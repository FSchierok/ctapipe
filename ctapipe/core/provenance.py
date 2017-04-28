"""
Provenance-related functionality

TODO: have this register whenever ctapipe is loaded

"""

import json
import logging
import platform
import sys
import uuid
from os.path import abspath
from contextlib import contextmanager

import ctapipe
import numpy as np
import psutil
from astropy.time import Time

from .support import Singleton

log = logging.getLogger(__name__)

__all__ = ['Provenance']


class Provenance(metaclass=Singleton):
    """
    Manage the provenance info for a stack of *activities*

    use `start_activity(name)` to start an activity. Any calls to
    `add_input_entity()` or `add_output_entity()` will register files within
    that activity. Finish the current activity with `finish_activity()`.

    Nested activities are allowed, and handled as a stack. The final output
    is not hierarchical, but a flat list of activities (however hierarchical
    activities could easily be implemented if necessary)
    """

    def __init__(self):
        self._activities = []  # stack of active activities
        self._finished_activities = []

    def start_activity(self, activity_name=sys.executable):
        """ push activity onto the stack"""
        activity = _ActivityProvenance(activity_name)
        activity.start()
        self._activities.append(activity)
        log.debug("started activity: {}".format(activity_name))

    def add_input_file(self, filename):
        """ register an input to the current activity """
        self.current_activity.register_input(abspath(filename))
        log.debug("added input entity '{}' to activity: '{}'".format(
            filename, self.current_activity.name))

    def add_output_file(self, filename):
        """ register an output to the current activity """
        self.current_activity.register_output(abspath(filename))
        log.debug("added output entity '{}' to activity: '{}'".format(
            filename, self.current_activity.name))

    def finish_activity(self, activity_name=None):
        """ end the current activity """
        activity = self._activities.pop()
        if activity_name is not None and activity_name != activity.name:
            raise ValueError("Tried to end activity '{}', but '{}' is current "
                             "activity".format(activity_name, activity.name))

        activity.finish()
        self._finished_activities.append(activity)
        log.debug("finished activity: {}".format(activity.name))

    @contextmanager
    def activity(self, name):
        """ context manager for activities """
        self.start_activity(name)
        yield
        self.finish_activity(name)

    @property
    def current_activity(self):
        if len(self._activities) == 0:
            log.warning("No activity has been started... starting a default "
                        "one")
            self.start_activity()
        return self._activities[-1]  # current activity as at the top of stack

    @property
    def provenance(self):
        """ returns provenence for full list of activities """
        return [x.provenance for x in self._finished_activities]

    def as_json(self, **kwargs):
        """ return all finished provenance as JSON.  Kwargs for `json.dumps`
        may be included, e.g. `indent=4`"""
        return json.dumps(self.provenance, **kwargs)

    @property
    def active_activity_names(self):
        return [x.name for x in self._activities]

    @property
    def finished_activity_names(self):
        return [x.name for x in self._finished_activities]

    def clear(self):
        """ remove all tracked activities """
        self._activities = []
        self._finished_activities = []


class _ActivityProvenance:
    """
    Low-level helper class to collect provenance information for a given
    *activity*.  Users should use `Provenance` as a top-level API, 
    not this class directly.
    """

    def __init__(self, activity_name=sys.executable):
        self._prov = {
            'activity_name': activity_name,
            'activity_uuid': str(uuid.uuid4()),
            'start': {},
            'stop': {},
            'system': {},
            'input': [],
            'output': []
        }
        self.name = activity_name

    def start(self):
        """ begin recording provenance for this activity. Set's up the system
        and startup provenance data. Generally should be called at start of a
        program."""
        self._prov['start'].update(_sample_cpu_and_memory())
        self._prov['system'].update(_get_system_provenance())

    def register_input(self, url):
        """
        Add a URL of a file to the list of inputs (can be a filename or full
        url, if no URL specifier is given, assume 'file://')

        Parameters
        ----------
        url: str
            filename or url of input file
        """
        self._prov['input'].append(url)

    def register_output(self, url):
        """
        Add a URL of a file to the list of outputs (can be a filename or full
        url, if no URL specifier is given, assume 'file://')

        Parameters
        ----------
        url: str
            filename or url of output file
        """
        self._prov['output'].append(url)

    def finish(self):
        """ record final provenance information, normally called at shutdown."""
        self._prov['stop'].update(_sample_cpu_and_memory())

        # record the duration (wall-clock) for this activity
        t_start = Time(self._prov['start']['time_utc'], format='isot')
        t_stop = Time(self._prov['stop']['time_utc'], format='isot')
        self._prov['duration_min'] = (t_stop - t_start).to('min').value

    def sample_cpu_and_memory(self):
        """
        Record a snapshot of current CPU and memory information.
        """
        if 'samples' not in self._prov:
            self._prov['samples'] = []
        self._prov['samples'].append(_sample_cpu_and_memory())

    @property
    def provenance(self):
        return self._prov


def _get_system_provenance():
    """ return JSON string containing provenance for all things that are
    fixed during the runtime"""

    bits, linkage = platform.architecture()

    return dict(
        ctapipe_version=ctapipe.__version__,
        executable=sys.executable,
        platform=dict(
            architecture_bits=bits,
            architecture_linkage=linkage,
            machine=platform.machine(),
            processor=platform.processor(),
            node=platform.node(),
            version=platform.version(),
            system=platform.system(),
            release=platform.release(),
            libcver=platform.libc_ver(),
            num_cpus=psutil.cpu_count(),
            boot_time=Time(psutil.boot_time(), format='unix').isot,
        ),
        python=dict(
            version_string=sys.version,
            version=platform.python_version_tuple(),
            compiler=platform.python_compiler(),
            implementation=platform.python_implementation(),
        ),
        arguments=sys.argv,
        start_time_utc=Time.now().isot,
    )


def _sample_cpu_and_memory():
    # times = np.asarray(psutil.cpu_times(percpu=True))
    # mem = psutil.virtual_memory()

    return dict(
        time_utc=Time.now().utc.isot,
        # memory=dict(total=mem.total,
        #             inactive=mem.inactive,
        #             available=mem.available,
        #             free=mem.free,
        #             wired=mem.wired),
        # cpu=dict(ncpu=psutil.cpu_count(),
        #          user=list(times[:, 0]),
        #          nice=list(times[:, 1]),
        #          system=list(times[:, 2]),
        #          idle=list(times[:, 3])),
    )
