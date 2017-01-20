# -*- coding: utf-8 -*-
# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from datetime import datetime, date, time, timedelta
import time
import os
import pwd
import socket
import json

import sys

from influxdb import InfluxDBClient

from ansible.plugins.callback import CallbackBase

class CallbackModule(CallbackBase):
    """
    This callback module fills an influxdb with Ansible events, :
    1. Create an empty list at the beginning of playbooks;
    2. Add an event to the list for each playbook/play/task;
    3. Connect to influxdb at the end of playbooks if succeeded and commit
    events.
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'influxdb_events'
    CALLBACK_NEEDS_WHITELIST = False

    def __init__(self):

        super(CallbackModule, self).__init__()

        self.events = []
        self.playbook = None
        self.playbook_name = None

    def report_event(self, event_type, fields):
        """
        Add a new event in the list
        """
        tags={}
        tags['type'] = event_type
        tags['user']= tags.get('user', self.username)
        tags['hostname'] = tags.get('hostname', self.hostname)
        current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')
        event = [
            {
                'time': current_time,
                'measurement': 'events',
                'tags': tags,
                'fields': fields
            }
        ]
        self.events.append(event)

    def v2_playbook_on_start(self, playbook):
        """
        Logs each playbook start
        """
        self.username = pwd.getpwuid(os.getuid()).pw_name
        self.hostname = socket.gethostname()
        self.playbook = playbook
        self.playbook_name = os.path.basename(playbook._file_name)
        self.playbook_basedir = playbook._basedir

        fields = {
            'text': 'Playbook %s started on %s by %s' %
               (self.playbook_name, self.hostname, self.username)
        }
        self.report_event('playbook-start', fields)

    def v2_playbook_on_play_start(self, play):
        """
        Logs each play start
        """

        fields = {
            'text': '"%s" from playbook %s started on %s by %s' %
                (play.name, self.playbook_name, self.hostname, self.username),
        }
        self.report_event('play-start', fields)

    def v2_playbook_on_task_start(self, task, is_conditional):
        """
        Logs each task start
        """
        fields = {
            'text': 'Task %s started on %s by %s' %
                (task.name, self.hostname, self.username)
        }
        self.report_event('task-start', fields)

    def v2_playbook_on_stats(self, stats):
        """
        Connect to influxdb and commit events
        """
        try:
            variable_manager = self.playbook._entries[0]._variable_manager
            extra_vars = variable_manager.extra_vars
            _host = extra_vars['influx_vip']
        except:
            _host = os.getenv('influx_vip')
            if not _host:
                self._display.warning("\
                    Couldn't find influxdb VIP in %s playbook\n\
                    please export the following environment\
                    variable: 'influx_vip'" %
                    (self.playbook_name, _host, os.path.basename(__file__)) )
                return
        _port = "8086"
        _user = "None"
        _pass = "None"
        _dbname = "events"
        try:
            self.influxdb = InfluxDBClient(_host, _port, _user, _pass, _dbname)
        except:
            """
            If influxdb is not reachable, this plugin is disabled
            ansible will not call any callback if disabled is set to True
            """
            self.disabled = True
            self._display.warning("influxdb was not reachable in %s playbook\n\
                please check the connectivity with %s\n\
                the plugin %s is thus disabled" %
                    (self.playbook_name, _host, os.path.basename(__file__)) )
            return
        self.influxdb.switch_database(_dbname)
        self.influxdb.switch_user(_user, _pass)

        for event in self.events:
            self.influxdb.write_points(event, time_precision='u')

