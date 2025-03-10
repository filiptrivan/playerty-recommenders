"""
An example based off the MovieLens 20M dataset.

This code will automatically download a HDF5 version of this
dataset when first run. The original dataset can be found here:
https://grouplens.org/datasets/movielens/.

Since this dataset contains explicit 5-star ratings, the ratings are
filtered down to positive reviews (4+ stars) to construct an implicit
dataset
"""

from __future__ import print_function

import argparse
import codecs
import logging
import time

import numpy as np
import tqdm

from implicit.als import AlternatingLeastSquares
from implicit.bpr import BayesianPersonalizedRanking
from implicit.datasets.movielens import get_movielens
from implicit.lmf import LogisticMatrixFactorization
from implicit.nearest_neighbours import (
    BM25Recommender,
    CosineRecommender,
    TFIDFRecommender,
    bm25_weight,
)

log = logging.getLogger("implicit")


def calculate_similar_movies(output_filename, model_name="als", min_rating=4.0, variant="100k"):
    # read in the input data file
    start = time.time()
    titles, ratings = get_movielens(variant)

    # remove things < min_rating, and convert to implicit dataset
    # by considering ratings as a binary preference only
    # FT: I don't need this
    # ratings.data[ratings.data < min_rating] = 0
    # ratings.eliminate_zeros()
    # ratings.data = np.ones(len(ratings.data))

    log.info("read data file in %s", time.time() - start)

    # generate a recommender model based off the input params
    if model_name == "als":
        model = AlternatingLeastSquares()

        # lets weight these models by bm25weight.
        log.debug("weighting matrix by bm25_weight")
        ratings = (bm25_weight(ratings, B=0.9) * 5).tocsr()

    user_ratings = ratings.T.tocsr()

    # train the model
    log.debug("training model %s", model_name)
    start = time.time()
    model.fit(user_ratings)
    log.debug("trained model '%s' in %s", model_name, time.time() - start)
    log.debug("calculating top movies")

    user_count = np.ediff1d(ratings.indptr)
    # >>> x = np.array([1, 2, 4, 7, 0])
    # >>> np.ediff1d(x)
    # array([ 1,  2,  3, -7])
    # [0, 2, 3, 3] -> [2, 1, 0]
    to_generate = sorted(np.arange(len(titles)), key=lambda x: -user_count[x])

    log.debug("calculating similar movies")
    with tqdm.tqdm(total=len(to_generate)) as progress:
        with codecs.open(output_filename, "w", "utf8") as o:
            batch_size = 1000
            for startidx in range(0, len(to_generate), batch_size):
                batch = to_generate[startidx : startidx + batch_size]
                ids, scores = model.similar_items(batch, 11)
                for i, movieid in enumerate(batch):
                    # if this movie has no ratings, skip over (for instance 'Graffiti Bridge' has
                    # no ratings > 4 meaning we've filtered out all data for it.
                    if ratings.indptr[movieid] != ratings.indptr[movieid + 1]:
                        title = titles[movieid]
                        for other, score in zip(ids[i], scores[i]):
                            o.write(f"{title}\t{titles[other]}\t{score}\n")
                progress.update(len(batch))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generates related movies from the MovieLens 20M "
        "dataset (https://grouplens.org/datasets/movielens/20m/)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--output",
        type=str,
        default="similar-movies.tsv",
        dest="outputfile",
        help="output file name",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="als",
        dest="model",
        help="model to calculate (als/bm25/tfidf/cosine)",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default="20m",
        dest="variant",
        help="Whether to use the 20m, 10m, 1m or 100k movielens dataset",
    )
    parser.add_argument(
        "--min_rating",
        type=float,
        default=4.0,
        dest="min_rating",
        help="Minimum rating to assume that a rating is positive",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    calculate_similar_movies(
        args.outputfile, model_name=args.model, min_rating=args.min_rating, variant=args.variant
    )