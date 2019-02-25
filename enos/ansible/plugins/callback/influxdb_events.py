# -*- coding: utf-8 -*-
# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from datetime import datetime
import pwd
import os
from requests import exceptions 

from ansible.plugins.callback import CallbackBase

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBServerError

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



    def v2_playbook_on_start(self, playbook):
        """Log each starting playbook"""

        self.playbook_name = os.path.basename(playbook._file_name)

        fields = {
            'tags': 'playbook %s' % self.username,
            'text': self.playbook_name,
            'type': 'playbook',
            'title': self.playbook_name
        }

        self.report_event(fields)


    def v2_playbook_on_play_start(self, play):
        """Log each starting play"""

        self.vm = play.get_variable_manager()
        # record the current play
        self.play = play

        fields = {
            'tags': 'play {} {}'.format(
                self.playbook_name,
                self.play.name),
            'title': play.name,
            'type': 'play',
            'text': play.name
        }

        self.report_event(fields)


    def v2_playbook_on_task_start(self, task, is_conditional):
        """Restart the timer when a task starts"""
        self.timer = datetime.now()

        fields = {
            'tags': 'task {} {} {}'.format(
               self.playbook_name,
               self.play.name,
               task.get_name()),
            'text': task.get_name(),
            'type': 'task',
            'title': task.get_name()
        }

        self.report_event(fields)

    def v2_runner_on_ok(self, result):
        """Log each finished task marked as 'changed'"""
        pass
        # Keeping the following for the record
        # Log only "changed" tasks
#        if not result.is_changed():
#            return
#
#        # Record the time at the end of a task
#        end_timer = datetime.now()
#        m, s = divmod((end_timer - self.timer).seconds, 60)
#        h, m = divmod(m, 60)
#
#        taskname = result._task.get_name()
#        hostname = result._host
#
#        fields = {
#            'tags': 'task %s %s %02d:%02d:%02d' % (
#                self.username,
#                hostname,
#                h, m, s),
#            'text': taskname,
#            'type': 'task',
#            'title': 'Task Succeeded'
#        }
#
#        self.report_event(fields)
#

    def v2_playbook_on_stats(self, stats):
        """Connect to InfluxDB and commit events"""
        # Get external tags if any
        enos_tags = self.vm.get_vars().get('enos_tags', '')
        fields = {
            'tags': 'playbook {} {}'.format(
               self.playbook_name, enos_tags),
            'text': 'playbook finished',
            'type': 'playbook',
            'title': self.playbook_name
        }
        self.report_event(fields)

        # Set InfluxDB host from an environment variable if provided
        _host = os.getenv('INFLUX_VIP') or self.vm.get_vars().get('influx_vip')
        if not _host:
            return
        _port = "8086"
        _user = "None"
        _pass = "None"
        _dbname = "events"
        influxdb = InfluxDBClient(_host, _port, _user, _pass, _dbname)
        try:
            version = influxdb.ping()                        
        except (InfluxDBServerError,
                exceptions.HTTPError,
                exceptions.ConnectionError,
                exceptions.Timeout,
                exceptions.RequestException) as error:

                return

        try:
            influxdb.write_points(self.events, time_precision='u')
        except Exception:
            # Disable the plugin if writes fail
            self.disabled = True
            self._display.warning(
                "Cannot write to InfluxDB, check the service state "
                "on %s." % _host)
            return

