#!/bin/bash
set -e
set -o pipefail

TAG=`git describe --tags $(git rev-list --tags --max-count=1)`
NUMCORES=`nproc --all`

mkdir -p VARIANT_CALLING/ref_test_data

docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION -v $PWD:$PWD -w $PWD $1/awscli:v0.0.1 \
  aws s3 cp s3://singlecelltestsets/TESTDATA_CODEBUILD/variant-calling VARIANT_CALLING/ref_test_data/ --recursive --quiet

docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_variant:$TAG \
  single_cell variant_calling --input_yaml single_cell/tests/codebuild/variant_calling/inputs.yaml \
  --maxjobs $NUMCORES --nocleanup --sentinel_only  \
  --submit local --loglevel DEBUG \
  --tmpdir VARIANT_CALLING/temp \
  --pipelinedir VARIANT_CALLING/pipeline --submit local --out_dir VARIANT_CALLING/output \
  --config_override '{"variant_calling": {"chromosomes": ["6", "8", "17"]}, "version": '\"$TAG\"'}'

docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_variant:$TAG \
  python single_cell/tests/codebuild/variant_calling/test_variant_calling.py VARIANT_CALLING/output VARIANT_CALLING/ref_test_data/refdata

docker run -w $PWD -v $PWD:$PWD --rm $1/single_cell_pipeline_variant:$TAG rm -rf VARIANT_CALLING
