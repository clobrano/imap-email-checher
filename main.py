#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vi: set ft=python :
'''
Usage:
    ./imap-email-checker [--config=PATH] [--verbose]

Options:
    -h --help                   Show this screen
    --config=PATH               Path to configuration file [default: ~/.imap-checker]
    -v, --verbose               Verbose mode for debugging purpose
'''

import sys
import os
import re
import imaplib
import json
import logging
import webbrowser

from docopt import docopt
import notify2 as pynotify
import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
LOG = logging.getLogger(__name__)


def get_configuration(filepath: str) -> str:
    '''Get configuration from file'''
    try:
        with open(filepath, 'r') as conf_file:
            configuration_str = conf_file.read()
        configuration = json.loads(configuration_str)
    except IOError as io_error:
        configuration = {}
        LOG.error('could not read configuration file: %s', io_error)
        print('configuration file is needed with the following format:')
        print('''{
    "email": "name.surname@company.com",
    "server": "imap-server.com",
    "password": "xxxx",
    "time": "120",
    "notify": "on",
    "browser_url": ""
    "folders": ["INBOX", "Do not remove INBOX", "Another Folder"]
}''')
        sys.exit(1)

    return configuration


def ignore_cb(notification, action: str):
    '''Ignore notification'''
    notification.set_data('ignore', True)
    notification.close()


def open_browser_cb(notification):
    '''Open notification in browser'''
    if not notification.get_data('ignore'):
        url = notification.get_data('browser_url')
        webbrowser.open_new_tab(url)
    notification.close()


def check_emails(account: dict) -> bool:
    '''Check unseen emails'''
    conn = imaplib.IMAP4_SSL(account['server'])

    ret, _ = conn.login(account['email'], account['password'])

    if ret != 'OK':
        LOG.fatal('could not log-in into account %s: %s', account['email'],
                  ret)

        return GLib.SOURCE_REMOVE

    report = dict()

    for folder in account['folders']:
        ret, _ = conn.select(folder)

        if ret != 'OK':
            LOG.error('could not select folder %s: %s', folder, ret)

            continue

        ret, data = conn.status(folder, '(UNSEEN)')

        if ret != 'OK':
            LOG.error('could not check folder %s: %s', folder, ret)

            continue

        conn.close()

        unseen = int(re.search('[0-9]+', data[0].decode('utf-8')).group(0))
        LOG.debug('%d unseen email(s) in %s', unseen, folder)

        if unseen:
            report[folder] = unseen

    ret, _ = conn.logout()

    if ret != 'BYE':
        LOG.warning('could not logout: %s', ret)

    unseen = sum([unseen for unseen in report.values()])

    if unseen and unseen != account['unseen']:
        account['unseen'] = unseen

        LOG.debug("%d unseen e-email(s)", unseen)

        if account['notify'] == 'on':
            message = '{} unseen e-mails'.format(unseen)
            icon = '/usr/share/icons/Adwaita/scalable/status/mail-unread-symbolic.svg'
            notification = pynotify.Notification('PyEmail', message, icon)
            notification.set_timeout(pynotify.EXPIRES_NEVER)

            server_capabilities = pynotify.get_server_caps()

            if 'actions' in server_capabilities:
                notification.add_action('close', 'Close', ignore_cb)
                notification.set_data('browser_url', account['browser_url'])
                notification.set_data('ignore', False)
                notification.connect('closed', open_browser_cb)

            notification.show()

    return GLib.SOURCE_CONTINUE


def main():
    '''Main function'''
    arguments = docopt(__doc__)

    if arguments['--verbose']:
        LOG.setLevel(logging.DEBUG)

    config_file = os.path.expanduser(arguments['--config'])
    account = get_configuration(config_file)
    account['unseen'] = 0

    pynotify.init('PyEmail', 'glib')
    check_emails(account)

    mainloop = GLib.MainLoop()
    event_id = GLib.timeout_add_seconds(
        int(account['time']), check_emails, account)

    if not event_id:
        LOG.fatal('could not setup e-mail checker function')
        sys.exit(1)

    mainloop.run()


if __name__ == '__main__':
    main()
