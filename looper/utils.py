""" Helpers without an obvious logical home. """

from collections import defaultdict, Iterable
import copy
import glob
import logging
import os

from pep import \
    FLAGS, SAMPLE_INDEPENDENT_PROJECT_SECTIONS, SAMPLE_NAME_COLNAME


_LOGGER = logging.getLogger(__name__)



def create_looper_args_text(pl_key, submission_settings, prj):
    """

    :param str pl_key: Strict/exact pipeline key, the hook into the project's
        pipeline configuration data
    :param dict submission_settings: Mapping from settings
        key to value, used to determine resource request
    :param Project prj: Project data, used for metadata and pipeline
        configuration information
    :return str: text representing the portion of a command generated by
        looper options and arguments
    """

    # Start with copied settings and empty arguments text
    submission_settings = copy.deepcopy(submission_settings)
    opt_arg_pairs = [("-O", prj.metadata.results_subdir)]

    if hasattr(prj, "pipeline_config"):
        # Index with 'pl_key' instead of 'pipeline'
        # because we don't care about parameters here.
        if hasattr(prj.pipeline_config, pl_key):
            # First priority: pipeline config in project config
            pl_config_file = getattr(prj.pipeline_config, pl_key)
            # Make sure it's a file (it could be provided as null.)
            if pl_config_file:
                if not os.path.isfile(pl_config_file):
                    _LOGGER.error(
                        "Pipeline config file specified "
                        "but not found: %s", pl_config_file)
                    raise IOError(pl_config_file)
                _LOGGER.info("Found config file: %s", pl_config_file)
                # Append arg for config file if found
                opt_arg_pairs.append(("-C", pl_config_file))

    num_cores = int(submission_settings.setdefault("cores"))
    if num_cores > 1:
        opt_arg_pairs.append(("-P", num_cores))

    try:
        mem_alloc = submission_settings["mem"]
    except KeyError:
        _LOGGER.warn("Submission settings lack memory specification")
    else:
        if float(mem_alloc) > 1:
            opt_arg_pairs.append(("-M", mem_alloc))

    looper_argtext = " ".join(["{} {}".format(opt, arg)
                               for opt, arg in opt_arg_pairs])
    return looper_argtext



def fetch_flag_files(prj=None, results_folder="", flags=FLAGS):
    """
    Find all flag file paths for the given project.

    :param Project | AttributeDict prj: full Project or AttributeDict with
        similar metadata and access/usage pattern
    :param str results_folder: path to results folder, corresponding to the
        1:1 sample:folder notion that a looper Project has. That is, this
        function uses the assumption that if rootdir rather than project is
        provided, the structure of the file tree rooted at rootdir is such
        that any flag files to be found are not directly within rootdir but
        are directly within on of its first layer of subfolders.
    :param Iterable[str] | str flags: Collection of flag names or single flag
        name for which to fetch files
    :return Mapping[str, list[str]]: collection of filepaths associated with
        particular flag for samples within the given project
    :raise TypeError: if neither or both of project and rootdir are given
    """

    if not (prj or results_folder) or (prj and results_folder):
        raise TypeError("Need EITHER project OR rootdir")

    # Just create the filenames once, and pair once with flag name.
    flags = [flags] if isinstance(flags, str) else list(flags)
    flagfile_suffices = ["*{}.flag".format(f) for f in flags]
    flag_suffix_pairs = list(zip(flags, flagfile_suffices))

    # Collect the flag file paths by flag name.
    files_by_flag = defaultdict(list)

    if prj is None:
        for flag, suffix in flag_suffix_pairs:
            flag_expr= os.path.join(results_folder, "*", suffix)
            flags_present = glob.glob(flag_expr)
            files_by_flag[flag] = flags_present
    else:
        # Iterate over samples to collect flag files.
        for s in prj.samples:
            folder = sample_folder(prj, s)
            # Check each candidate flag for existence, collecting if present.
            for flag, suffix in flag_suffix_pairs:
                flag_expr = os.path.join(folder, suffix)
                flags_present = glob.glob(flag_expr)
                files_by_flag[flag].extend(flags_present)


    return files_by_flag



def grab_project_data(prj):
    """
    From the given Project, grab Sample-independent data.

    There are some aspects of a Project of which it's beneficial for a Sample
    to be aware, particularly for post-hoc analysis. Since Sample objects
    within a Project are mutually independent, though, each doesn't need to
    know about any of the others. A Project manages its, Sample instances,
    so for each Sample knowledge of Project data is limited. This method
    facilitates adoption of that conceptual model.

    :param Project prj: Project from which to grab data
    :return Mapping: Sample-independent data sections from given Project
    """

    if not prj:
        return {}

    data = {}
    for section in SAMPLE_INDEPENDENT_PROJECT_SECTIONS:
        try:
            data[section] = prj[section]
        except KeyError:
            _LOGGER.debug("Project lacks section '%s', skipping", section)

    return data



def sample_folder(prj, sample):
    """
    Get the path to this Project's root folder for the given Sample.

    :param AttributeDict | Project prj: project with which sample is associated
    :param Mapping sample: Sample or sample data for which to get root output
        folder path.
    :return str: this Project's root folder for the given Sample
    """
    return os.path.join(prj.metadata.results_subdir,
                        sample[SAMPLE_NAME_COLNAME])
