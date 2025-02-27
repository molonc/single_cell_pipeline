#!/bin/bash
set -e
set -o pipefail

TAG=`git describe --tags $(git rev-list --tags --max-count=1)`
NUMCORES=`nproc --all`

mkdir -p ANNOTATION/ref_test_data

docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION -v $PWD:$PWD -w $PWD $1/awscli:v0.0.1 \
  aws s3 cp s3://singlecelltestsets/TESTDATA_CODEBUILD/annotation ANNOTATION/ref_test_data --recursive --quiet

docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_annotation:$TAG \
  single_cell annotation --input_yaml single_cell/tests/codebuild/annotation/inputs.yaml \
  --library_id A97318A --maxjobs $NUMCORES --nocleanup --sentinel_only  \
  --submit local --loglevel DEBUG \
  --tmpdir ANNOTATION/temp \
  --pipelinedir ANNOTATION/pipeline \
  --submit local \
  --out_dir ANNOTATION/output \
  --config_override '{"annotation": {"chromosomes": ["6", "8", "17"]}}' \
  --no_corrupt_tree

docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_annotation:$TAG \
  python single_cell/tests/codebuild/annotation/test_annotation.py ANNOTATION/output A97318A  ANNOTATION/ref_test_data/refdata

docker run -w $PWD -v $PWD:$PWD --rm $1/single_cell_pipeline_annotation:$TAG rm -rf ANNOTATION
