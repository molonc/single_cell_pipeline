#!/bin/bash
set -e
set -o pipefail

TAG=`git describe --tags $(git rev-list --tags --max-count=1)`
NUMCORES=`nproc --all`

mkdir -p COUNT_HAPS/ref_test_data

docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION -v $PWD:$PWD -w $PWD $1/awscli:v0.0.1 \
  aws s3 cp s3://singlecelltestsets/TESTDATA_CODEBUILD/count-haps-new COUNT_HAPS/ref_test_data --recursive --quiet

docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_haplotypes:$TAG \
  single_cell count_haps \
  --input_yaml single_cell/tests/codebuild/count_haps/inputs.yaml \
  --maxjobs $NUMCORES \
  --nocleanup \
  --sentinel_only \
  --submit local \
  --loglevel DEBUG \
  --tmpdir COUNT_HAPS/temp \
  --config_override '{"count_haps":{"chromosomes":["15"], "extract_seqdata": {"genome_fai_template": "/refdata/human/infer_haps/GRCh37-lite.fa.fai", "genome_fasta_template": "/refdata/human/infer_haps/GRCh37-lite.fa"}, "ref_data_dir": "/refdata/human/infer_haps/"}}' \
  --pipelinedir COUNT_HAPS/pipeline \
  --submit local \
  --out_dir COUNT_HAPS/output


docker run -w $PWD -v $PWD:$PWD -v /refdata:/refdata --rm \
  $1/single_cell_pipeline_haplotypes:$TAG \
  python single_cell/tests/codebuild/count_haps/test_count_haps.py COUNT_HAPS/output COUNT_HAPS/ref_test_data

docker run -w $PWD -v $PWD:$PWD --rm $1/single_cell_pipeline_haplotypes:$TAG rm -rf COUNT_HAPS
