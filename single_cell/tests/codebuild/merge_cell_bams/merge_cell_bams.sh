#!/bin/bash
set -e
set -o pipefail

TAG=`git describe --tags $(git rev-list --tags --max-count=1)`
NUMCORES=`nproc --all`

mkdir -p MERGE_CELL_BAMS/ref_test_data


docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION -v $PWD:$PWD -w $PWD $1/awscli:v0.0.1 \
  aws s3 cp s3://singlecelltestsets/TESTDATA_CODEBUILD/merge-bams MERGE_CELL_BAMS/ref_test_data --recursive --quiet

docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_alignment:$TAG \
  single_cell merge_cell_bams \
  --input_yaml single_cell/tests/codebuild/merge_cell_bams/inputs.yaml \
  --maxjobs $NUMCORES --nocleanup --sentinel_only  \
  --submit local --loglevel DEBUG \
  --tmpdir MERGE_CELL_BAMS/temp \
  --pipelinedir MERGE_CELL_BAMS/pipeline \
  --submit local \
  --out_dir MERGE_CELL_BAMS/output --config_override '{"merge_bams": {"chromosomes": ["6", "8", "17"]}}'

docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_alignment:$TAG \
  python single_cell/tests/codebuild/merge_cell_bams/test_merge_cell_bams.py MERGE_CELL_BAMS/output MERGE_CELL_BAMS/ref_test_data/refdata

docker run -w $PWD -v $PWD:$PWD --rm $1/single_cell_pipeline_alignment:$TAG rm -rf MERGE_CELL_BAMS
