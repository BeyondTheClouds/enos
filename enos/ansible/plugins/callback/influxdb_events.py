# -*- coding: utf-8 -*-
# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from datetime import datetime
import os
import pwd

from influxdb import InfluxDBClient

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    """
    This callback module fills an InfluxDB with Ansible events:
    1. Create an empty list at the beginning of playbooks;
    2. Add an event to the list for each playbook/play/task;
    3. Connect to InfluxDB at the end of playbooks if succeeded and commit
    events.
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'influxdb_events'
    CALLBACK_NEEDS_WHITELIST = True


    def __init__(self):
        super(CallbackModule, self).__init__()

        self.timer = None
        self.events = []
        self.host_vars = None
        self.timer = None
        self.username = pwd.getpwuid(os.getuid()).pw_name


    def report_event(self, fields):
        """Add a new event in the list"""

        current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')

        event = {
            'time': current_time,
            'measurement': 'events',
            'fields': fields
        }

        self.events.append(event)


    def add_extra_tags(self, fields):
        """Add extra tags to the event"""

        # Add Kolla-related information in tags
        fields['tags'] = '%s %s %s %s' % (fields['tags'],
                self.host_vars.get('kolla_ref'),
                self.host_vars.get('kolla_base_distro') or \
                        self.host_vars['kolla']['kolla_base_distro'],
                self.host_vars.get('kolla_install_type') or \
                        self.host_vars['kolla']['kolla_install_type']
        )

        # Set the variables only available during the `os_install` phase
        if self.host_vars.get('openstack_release', 'auto') != 'auto':
            fields['tags'] = '%s %s' % (fields['tags'],
                    self.host_vars.get('openstack_release'))

        if 'openstack_region_name' in self.host_vars:
            fields['tags'] = '%s %s' % (fields['tags'],
                    self.host_vars.get('openstack_region_name'))


    def v2_playbook_on_start(self, playbook):
        """Log each starting playbook"""

        playbook_name = os.path.basename(playbook._file_name)

        fields = {
            'tags': 'playbook %s' % self.username,
            'text': playbook_name,
            'type': 'playbook',
            'title': 'Playbook Started'
        }

        self.report_event(fields)


    def v2_playbook_on_play_start(self, play):
        """Log each starting play"""

        host = play._variable_manager._hostvars.keys()[0]
        self.host_vars = play._variable_manager._hostvars[str(host)]

        if not self.host_vars.get('enable_monitoring', True):
            # Disable the plugin if InfluxDB is unreachable
            self.disabled = True
            self._display.warning("The plugin %s is disabled since "
                "monitoring is disabled in the config file." %
                self._original_path)

        fields = {
            'tags': 'play %s' % self.username,
            'text': play.name,
            'type': 'play',
            'title': 'Play Started'
        }

        self.add_extra_tags(fields)
        self.report_event(fields)


    def v2_playbook_on_task_start(self, task, is_conditional):
        """Restart the timer when a task starts"""

        self.timer = datetime.now()


    def v2_runner_on_ok(self, result):
        """Log each finished task marked as 'changed'"""

        # Log only "changed" tasks
        if not result.is_changed():
            return

        # Record the time at the end of a task
        end_timer = datetime.now()
        m, s = divmod((end_timer - self.timer).seconds, 60)
        h, m = divmod(m, 60)

        taskname = result._task.get_name()
        hostname = result._host

        fields = {
            'tags': 'task %s %s %02d:%02d:%02d' % (
                self.username,
                hostname,
                h, m, s),
            'text': taskname,
            'type': 'task',
            'title': 'Task Succeeded'
        }

        # Add the event tag if it is not the default value
        event_tag = result._task.tags[0]
        if event_tag != 'always':
            fields['tags'] = '%s %s' % (fields['tags'], event_tag)

        self.add_extra_tags(fields)
        self.report_event(fields)


    def v2_playbook_on_stats(self, stats):
        """Connect to InfluxDB and commit events"""

        # Set InfluxDB host from an environment variable if provided
        _host = os.getenv('influx_vip') or self.host_vars['influx_vip']
        _port = "8086"
        _user = "None"
        _pass = "None"
        _dbname = "events"
        influxdb = InfluxDBClient(_host, _port, _user, _pass, _dbname)

        try:
            influxdb.write_points(self.events, time_precision='u')
        except Exception:
            # Disable the plugin if writes fail
            self.disabled = True
            self._display.warning(
                "Cannot write to InfluxDB, check the service state "
                "on %s." % _host)
            return

