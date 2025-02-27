'''
Created on Feb 19, 2018

@author: dgrewal
'''
import errno
import gzip
import logging
import multiprocessing
import os
import re
import shutil
import tarfile

import pandas as pd
import pypeliner
import single_cell
import yaml


class InputException(Exception):
    pass


def is_empty(filepath):
    if get_file_format(filepath) == 'gzip':
        with gzip.open(filepath, 'rt') as reader:
            if reader.readline():
                return False
            else:
                return True
    else:
        if os.stat(filepath).st_size == 0:
            return True
        else:
            return False


def flatten(data):
    if isinstance(data, dict):
        data = data.values()
    return data


def generate_and_upload_metadata(
        command, root_dir, filepaths, output, template=None,
        input_yaml_data=None, input_yaml=None, metadata={}, type=None
):
    def __add_extensions(filepaths):
        paths_extensions = []
        for filepath in filepaths:
            paths_extensions.append(filepath)

            if filepath.endswith('.csv.gz'):
                paths_extensions.append(filepath + '.yaml')
            elif filepath.endswith('.vcf.gz'):
                paths_extensions.append(filepath + '.csi')
                paths_extensions.append(filepath + '.tbi')
            elif filepath.endswith('.bam'):
                paths_extensions.append(filepath + '.bai')

        return paths_extensions

    def __generate_meta_yaml_file(
            metadata_file,
            filepaths=None,
            metadata=None,
            root_dir=None
    ):
        if not root_dir:
            final_paths = filepaths
        else:
            final_paths = []
            for filepath in filepaths:
                if not filepath.startswith(root_dir):
                    error = 'file {} does not have {} in path'.format(
                        filepath, root_dir
                    )
                    raise Exception(error)

                filepath = os.path.relpath(filepath, root_dir)
                final_paths.append(filepath)

        final_paths = __add_extensions(final_paths)

        metadata = {
            'filenames': final_paths,
            'meta': metadata,
        }

        write_to_yaml(metadata_file, metadata)

    def __get_version():
        version = single_cell.__version__
        # strip setuptools metadata
        version = version.split("+")[0]
        return version

    if not metadata:
        metadata = {}

    if isinstance(filepaths, dict):
        filepaths = filepaths.values()
    filepaths = list(filepaths)

    metadata['command'] = ' '.join(command)
    metadata['version'] = __get_version()

    if type:
        metadata['type'] = type

    if template:
        assert len(template) == 3
        instances, template_path, instance_key = template
        assert re.match('.*\{.*\}.*', template_path)
        template_path = os.path.relpath(template_path, root_dir)
        metadata['bams'] = {}
        metadata['bams']['template'] = template_path
        instances = [{instance_key: instance} for instance in instances]
        metadata['bams']['instances'] = instances

    if input_yaml_data:
        if not input_yaml:
            raise InputException("missing yaml file to write to")
        with open(input_yaml, 'wt') as yaml_writer:
            yaml.safe_dump(input_yaml_data, yaml_writer)

        if not input_yaml.startswith(root_dir) and root_dir in input_yaml:
            input_yaml = input_yaml[input_yaml.index(root_dir):]
        if input_yaml.endswith('.tmp'):
            input_yaml = input_yaml[:-4]

        metadata['input_yaml'] = os.path.relpath(input_yaml, root_dir)
        filepaths.append(input_yaml)

    __generate_meta_yaml_file(
        output, filepaths=filepaths, metadata=metadata, root_dir=root_dir
    )


def copyfile(source, dest):
    shutil.copyfile(source, dest)


class getFileHandle(object):
    def __init__(self, filename, mode='rt'):
        self.filename = filename
        self.mode = mode

    def __enter__(self):
        if self.get_file_format(self.filename) in ["csv", 'plain-text']:
            self.handle = open(self.filename, self.mode)
        elif self.get_file_format(self.filename) == "gzip":
            self.handle = gzip.open(self.filename, self.mode)
        elif self.get_file_format(self.filename) == "h5":
            self.handle = pd.HDFStore(self.filename, self.mode)
        return self.handle

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.handle.close()

    def get_file_format(self, filepath):
        if filepath.endswith('.tmp'):
            filepath = filepath[:-4]

        _, ext = os.path.splitext(filepath)

        if ext == ".csv":
            return "csv"
        elif ext == ".gz":
            return "gzip"
        elif ext == ".h5" or ext == ".hdf5":
            return "h5"
        elif ext == '.yaml':
            return 'plain-text'
        else:
            logging.getLogger("single_cell.helpers").warning(
                "Couldn't detect output format. extension {}".format(ext)
            )
            return "plain-text"


def get_compression_type_pandas(filepath):
    if get_file_format(filepath) == 'gzip':
        return 'gzip'
    else:
        return None


def get_file_format(filepath):
    if filepath.endswith('.tmp'):
        filepath = filepath[:-4]

    _, ext = os.path.splitext(filepath)

    if ext == ".csv":
        return "csv"
    elif ext == ".gz":
        return "gzip"
    elif ext == ".h5" or ext == ".hdf5":
        return "h5"
    else:
        logging.getLogger("single_cell.plot_metrics").warning(
            "Couldn't detect output format. extension {}".format(ext)
        )
        return "csv"


def write_to_yaml(outfile, data):
    with open(outfile, 'w') as output:
        yaml.safe_dump(data, output, default_flow_style=False)


def eval_expr(val, operation, threshold):
    if operation == "gt":
        if val > threshold:
            return True
    elif operation == 'ge':
        if val >= threshold:
            return True
    elif operation == 'lt':
        if val < threshold:
            return True
    elif operation == 'le':
        if val <= threshold:
            return True
    elif operation == 'eq':
        if val == threshold:
            return True
    elif operation == 'ne':
        if not val == threshold:
            return True
    elif operation == 'in':
        if val in threshold:
            return True
    elif operation == 'notin':
        if not val in threshold:
            return True
    else:
        raise Exception("unknown operator type: {}".format(operation))

    return False


def filter_metrics(metrics, cell_filters):
    # cells to keep
    for metric_col, operation, threshold in cell_filters:
        if metrics.empty:
            continue

        rows_to_keep = metrics[metric_col].apply(eval_expr, args=(operation, threshold))

        metrics = metrics[rows_to_keep]

    return metrics


def get_incrementing_filename(path):
    """
    avoid overwriting files. if path exists then return path
    otherwise generate a path that doesnt exist.
    """

    if not os.path.exists(path):
        return path

    i = 0
    while os.path.exists("{}.{}".format(path, i)):
        i += 1

    return "{}.{}".format(path, i)


def build_shell_script(command, tag, tempdir):
    outfile = os.path.join(tempdir, "{}.sh".format(tag))
    with open(outfile, 'w') as scriptfile:
        scriptfile.write("#!/bin/bash\n")
        if isinstance(command, list) or isinstance(command, tuple):
            command = ' '.join(command) + '\n'
        scriptfile.write(command)
    return outfile


def run_in_gnu_parallel(commands, tempdir, ncores=None):
    makedirs(tempdir)

    scriptfiles = []

    for tag, command in enumerate(commands):
        scriptfiles.append(build_shell_script(command, tag, tempdir))

    parallel_outfile = os.path.join(tempdir, "commands.txt")
    with open(parallel_outfile, 'w') as outfile:
        for scriptfile in scriptfiles:
            outfile.write("sh {}\n".format(scriptfile))

    if not ncores:
        ncores = multiprocessing.cpu_count()

    gnu_parallel_cmd = ['parallel', '--jobs', ncores, '<', parallel_outfile]
    pypeliner.commandline.execute(*gnu_parallel_cmd)


def makedirs(directory, isfile=False):
    if isfile:
        directory = os.path.dirname(directory)
        if not directory:
            return

    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def extract_tar(input_tar, outdir):
    with tarfile.open(input_tar) as tar:
        tar.extractall(path=outdir)


def gunzip_file(infile, outfile):
    with gzip.open(infile, 'rb') as f_in:
        with open(outfile, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
