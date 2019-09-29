# Copyright (c) 2019, NVIDIA CORPORATION.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import pytest
from cuml.test.utils import get_handle
from cuml import DBSCAN as cuDBSCAN
from sklearn.cluster import DBSCAN as skDBSCAN
from sklearn.datasets.samples_generator import make_blobs
import pandas as pd
import cudf
import numpy as np
from sklearn.preprocessing import StandardScaler
from cuml.test.utils import fit_predict, get_pattern

from sklearn.metrics import adjusted_rand_score


def unit_param(*args, **kwargs):
    return pytest.param(*args, **kwargs, marks=pytest.mark.unit)


def quality_param(*args, **kwargs):
    return pytest.param(*args, **kwargs, marks=pytest.mark.quality)


def stress_param(*args, **kwargs):
    return pytest.param(*args, **kwargs, marks=pytest.mark.stress)


dataset_names = ['noisy_moons', 'varied', 'aniso', 'blobs',
                 'noisy_circles', 'no_structure']


@pytest.mark.parametrize('max_mbytes_per_batch', [1e9, 5e9])
@pytest.mark.parametrize('datatype', [np.float32, np.float64])
@pytest.mark.parametrize('input_type', ['ndarray'])
@pytest.mark.parametrize('use_handle', [True, False])
@pytest.mark.parametrize('nrows', [unit_param(20), quality_param(5000),
                         stress_param(500000)])
@pytest.mark.parametrize('ncols', [unit_param(3), quality_param(100),
                         stress_param(1000)])
@pytest.mark.parametrize('out_dtype', [unit_param("int32"),
                                       unit_param(np.int32),
                                       unit_param("int64"),
                                       unit_param(np.int64),
                                       unit_param("auto"),
                                       quality_param("auto"),
                                       stress_param("auto")])
def test_dbscan(datatype, input_type, use_handle,
                nrows, ncols, max_mbytes_per_batch, out_dtype):
    n_samples = nrows
    n_feats = ncols
    X, y = make_blobs(n_samples=n_samples, cluster_std=0.01,
                      n_features=n_feats, random_state=0)

    handle, stream = get_handle(use_handle)
    cudbscan = cuDBSCAN(handle=handle, eps=1, min_samples=2,
                        max_mbytes_per_batch=max_mbytes_per_batch)

    if input_type == 'dataframe':
        X = pd.DataFrame(
            {'fea%d' % i: X[0:, i] for i in range(X.shape[1])})
        X_cudf = cudf.DataFrame.from_pandas(X)
        cu_labels = cudbscan.fit_predict(X_cudf, out_dtype=out_dtype)
    else:
        cu_labels = cudbscan.fit_predict(X, out_dtype=out_dtype)

    if nrows < 500000:
        skdbscan = skDBSCAN(eps=1, min_samples=2, algorithm="brute")
        sk_labels = skdbscan.fit_predict(X)
        score = adjusted_rand_score(cu_labels, sk_labels)
        assert score == 1

    if out_dtype == "int32" or out_dtype == np.int32:
        assert cu_labels.dtype == np.int32
    elif out_dtype == "int64" or out_dtype == np.int64:
        assert cu_labels.dtype == np.int64


@pytest.mark.parametrize("name", [
                                 'noisy_moons',
                                 'blobs',
                                 'no_structure'])
@pytest.mark.parametrize('nrows', [unit_param(20), quality_param(5000),
                         stress_param(500000)])
def test_dbscan_sklearn_comparison(name, nrows):
    default_base = {'quantile': .3,
                    'eps': .5,
                    'damping': .9,
                    'preference': -200,
                    'n_neighbors': 10,
                    'n_clusters': 2}
    n_samples = nrows
    pat = get_pattern(name, n_samples)
    params = default_base.copy()
    params.update(pat[1])
    X, y = pat[0]

    X = StandardScaler().fit_transform(X)

    cuml_dbscan = cuDBSCAN(eps=params['eps'], min_samples=5)
    cu_y_pred, cu_n_clusters = fit_predict(cuml_dbscan,
                                           'cuml_DBSCAN', X)

    if nrows < 500000:
        dbscan = skDBSCAN(eps=params['eps'], min_samples=5)
        sk_y_pred, sk_n_clusters = fit_predict(dbscan,
                                               'sk_DBSCAN', X)

        score = adjusted_rand_score(sk_y_pred, cu_y_pred)
        assert(score == 1.0)


@pytest.mark.xfail(strict=True, raises=ValueError)
def test_dbscan_out_dtype_fails_invalid_input():
    X, _ = make_blobs(n_samples=100)

    cudbscan = cuDBSCAN()
    cudbscan.fit_predict(X, out_dtype="bad_input")
