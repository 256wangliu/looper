""" Tests for ProtocolInterface, for Project/PipelineInterface interaction. """

import __builtin__
import inspect
import logging
import mock
import os
import pytest
import yaml
import looper
from looper import models, DEV_LOGGING_FMT
from looper.models import ProtocolInterface


__author__ = "Vince Reuter"
__email__ = "vreuter@virginia.edu"



def _write_config_data(protomap, conf_data, dirpath):
    """
    Write ProtocolInterface data to (temp)file.

    :param Mapping protomap: mapping from protocol name to pipeline key/name
    :param Mapping conf_data: mapping from pipeline key/name to configuration
        data for a PipelineInterface
    :param str dirpath: path to filesystem location in which to place the
        file to write
    :return str: path to the (temp)file written
    """
    full_conf_data = {"protocol_mapping": protomap, "pipelines": conf_data}
    filepath = os.path.join(dirpath, "pipeline_interface.yaml")
    with open(filepath, 'w') as conf_file:
        yaml.safe_dump(full_conf_data, conf_file)
    return filepath



@pytest.fixture(scope="function")
def path_config_file(request, tmpdir, atac_pipe_name):
    """
    Write PipelineInterface configuration data to disk.

    Grab the data from the test case's appropriate fixture. Also check the
    test case parameterization for pipeline path specification, adding it to
    the configuration data before writing to disk if the path specification is
    present

    :param pytest._pytest.fixtures.SubRequest request: test case requesting
        this fixture
    :param py.path.local.LocalPath tmpdir: temporary directory fixture
    :param str atac_pipe_name: name/key for ATAC-Seq pipeline; this should
        also be used by the requesting test case if a path is to be added;
        separating the name from the folder path allows parameterization of
        the test case in terms of folder path, with pipeline name appended
        after the fact (that is, the name fixture can't be used in the )
    :return str: path to the configuration file written
    """
    conf_data = request.getfixturevalue("atacseq_piface_data")
    if "pipe_path" in request.fixturenames:
        pipeline_dirpath = request.getfixturevalue("pipe_path")
        pipe_path = os.path.join(pipeline_dirpath, atac_pipe_name)
        # Pipeline key/name is mapped to the interface data; insert path in
        # that Mapping, not at the top level, in which name/key is mapped to
        # interface data bundle.
        for iface_bundle in conf_data.values():
            iface_bundle["path"] = pipe_path
    return _write_config_data(protomap={"ATAC": atac_pipe_name},
                              conf_data=conf_data, dirpath=tmpdir.strpath)



class PipelinePathResolutionTests:
    """ Project requests pipeline information via an interface key. """


    def test_no_path(self, atacseq_piface_data,
                     path_config_file, atac_pipe_name):
        """ Without explicit path, pipeline is assumed parallel to config. """

        piface = ProtocolInterface(path_config_file)

        # The pipeline is assumed to live alongside its configuration file.
        config_dirpath = os.path.dirname(path_config_file)
        expected_pipe_path = os.path.join(config_dirpath, atac_pipe_name)

        _, full_pipe_path, _ = \
                piface.finalize_pipeline_key_and_paths(atac_pipe_name)
        assert expected_pipe_path == full_pipe_path


    def test_relpath_with_dot_becomes_absolute(
            self, tmpdir, atac_pipe_name, atacseq_piface_data):
        """ Leading dot drops from relative path, and it's made absolute. """
        path_parts = ["relpath", "to", "pipelines", atac_pipe_name]
        sans_dot_path = os.path.join(*path_parts)
        pipe_path = os.path.join(".", sans_dot_path)
        atacseq_piface_data[atac_pipe_name]["path"] = pipe_path

        exp_path = os.path.join(tmpdir.strpath, sans_dot_path)

        path_config_file = _write_config_data(
                protomap={"ATAC": atac_pipe_name},
                conf_data=atacseq_piface_data, dirpath=tmpdir.strpath)
        piface = ProtocolInterface(path_config_file)
        _, obs_path, _ = piface.finalize_pipeline_key_and_paths(atac_pipe_name)
        # Dot may remain in path, so assert equality of absolute paths.
        assert os.path.abspath(exp_path) == os.path.abspath(obs_path)


    @pytest.mark.parametrize(
            argnames="pipe_path", argvalues=["relative/pipelines/path"])
    def test_non_dot_relpath_becomes_absolute(
            self, atacseq_piface_data, path_config_file,
            tmpdir, pipe_path, atac_pipe_name):
        """ Relative pipeline path is made absolute when requested by key. """
        # TODO: constant-ify "path" and "ATACSeq.py", as well as possibly "pipelines"
        # and "protocol_mapping" section names of PipelineInterface
        exp_path = os.path.join(
                tmpdir.strpath, pipe_path, atac_pipe_name)
        piface = ProtocolInterface(path_config_file)
        _, obs_path, _ = piface.finalize_pipeline_key_and_paths(atac_pipe_name)
        assert exp_path == obs_path


    @pytest.mark.parametrize(
            argnames=["pipe_path", "expected_path_base"],
            argvalues=[(os.path.join("$HOME", "code-base-home", "biopipes"),
                        os.path.join(os.path.expandvars("$HOME"),
                                "code-base-home", "biopipes")),
                       (os.path.join("~", "bioinformatics-pipelines"),
                        os.path.join(os.path.expanduser("~"),
                                     "bioinformatics-pipelines"))])
    def test_absolute_path(
            self, atacseq_piface_data, path_config_file, tmpdir, pipe_path,
            expected_path_base, atac_pipe_name):
        """ Absolute path regardless of variables works as pipeline path. """
        exp_path = os.path.join(
                tmpdir.strpath, expected_path_base, atac_pipe_name)
        piface = ProtocolInterface(path_config_file)
        _, obs_path, _ = piface.finalize_pipeline_key_and_paths(atac_pipe_name)
        assert exp_path == obs_path


    @pytest.mark.xfail(
            condition=models._LOGGER.getEffectiveLevel() < logging.WARN,
            reason="Insufficient logging level to capture warning message: {}".
                   format(models._LOGGER.getEffectiveLevel()))
    @pytest.mark.parametrize(
        argnames="pipe_path",
        argvalues=["nonexistent.py", "path/to/missing.py",
                   "/abs/path/to/mythical"])
    def test_warns_about_nonexistent_pipeline_script_path(
            self, atacseq_piface_data, path_config_file,
            tmpdir, pipe_path, atac_pipe_name):
        """ Nonexistent, resolved pipeline script path generates warning. """
        name_log_file = "temp-test-log.txt"
        path_log_file = os.path.join(tmpdir.strpath, name_log_file)
        temp_hdlr = logging.FileHandler(path_log_file, mode='w')
        fmt = logging.Formatter(DEV_LOGGING_FMT)
        temp_hdlr.setFormatter(fmt)
        temp_hdlr.setLevel(logging.WARN)
        models._LOGGER.handlers.append(temp_hdlr)
        pi = ProtocolInterface(path_config_file)
        pi.finalize_pipeline_key_and_paths(atac_pipe_name)
        with open(path_log_file, 'r') as logfile:
            loglines = logfile.readlines()
        assert 1 == len(loglines)
        logmsg = loglines[0]
        assert "WARN" in logmsg and pipe_path in logmsg



class SampleSubtypeTests:
    """ ProtocolInterface attempts import of pipeline-specific Sample. """

    # Basic cases
    # 1 -- unmapped pipeline
    # 2 -- subtypes section is single string
    # 3 -- subtypes section is mapping ()
    # 4 -- subtypes section is missing (use single Sample subclass if there is one, base Sample for 0 or > 1 Sample subtypes defined)
    # 5 -- subtypes section is null  --> ALWAYS USE BASE SAMPLE (backdoor user side mechanism for making this be so)

    # Import trouble cases
    # No __main__
    # Argument parsing
    # missing import(s)

    # Subcases
    # 2 -- single string
    # 2a -- named class isn't defined in the module
    # 2b -- named class is in module but isn't defined
    #

    @pytest.fixture(scope="function")
    def subtypes_section_single(self, atac_pipe_name):
        pass


    @pytest.fixture(scope="function")
    def subtypes_section_multiple(self, atac_pipe_name):
        pass


    @pytest.mark.parametrize(
            argnames="pipe_key",
            argvalues=["ATAC-Seq.py", "atacseq.py", "ATACSEQ.py", "ATACSEQ",
                       "atacseq", "ATAC-seq.py", "ATACseq.py"])
    @pytest.mark.parametrize(
            argnames="protocol",
            argvalues=["ATAC-Seq", "ATACSeq", "ATACseq", "ATAC-seq", "ATAC",
                       "ATACSEQ", "ATAC-SEQ", "atac", "atacseq", "atac-seq"])
    def test_pipeline_key_close_matches_dont_count(
            self, tmpdir, pipe_key, protocol, atac_pipe_name,
            atacseq_iface_with_resources):
        """ Request for Sample subtype for unmapped pipeline is KeyError. """
        strict_pipe_key = atac_pipe_name
        protocol_mapping = {protocol: strict_pipe_key}
        path_config_file = _write_config_data(
                protomap=protocol_mapping,
                conf_data={strict_pipe_key: atacseq_iface_with_resources},
                dirpath=tmpdir.strpath)
        piface = ProtocolInterface(path_config_file)
        full_pipe_path = os.path.join(tmpdir.strpath, atac_pipe_name)
        with pytest.raises(KeyError):
            # Mismatch between pipeline key arg and strict key --> KeyError.
            piface.fetch_sample_subtype(
                    protocol, pipe_key, full_pipe_path=full_pipe_path)


    def test_protocol_match_is_fuzzy(self):
        """ Punctuation and case mismatches are tolerated in protocol name. """
        pass


    @pytest.mark.parametrize(
            argnames="error_type",
            argvalues=zip(*inspect.getmembers(
                    __builtin__, lambda o: inspect.isclass(o) and
                                           issubclass(o, BaseException)))[1])
    def test_problematic_import_builtin_exception(self, error_type):
        pass


    @pytest.mark.parametrize(
            argnames="error_type",
            argvalues=zip(*inspect.getmembers(
                    looper.models, lambda o: inspect.isclass(o) and
                                             issubclass(o, Exception)))[1])
    def test_problematic_import_custom_exception(self, error_type):
        pass


    def test_no_subtypes_section(self):
        pass


    def test_subtypes_section_maps_protocol_to_non_sample_subtype(self):
        pass


    def test_subtypes_section_single_subtype_name_is_sample_subtype(self):
        pass


    def test_subtypes_section_single_subtype_name_is_not_sample_subtype(self):
        pass


    def test_subtypes_section_mapping_missing_protocol(self):
        pass
