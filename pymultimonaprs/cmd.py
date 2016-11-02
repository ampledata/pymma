#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""pymultimonaprs Package."""

import argparse
import json
import logging
import logging.handlers
import signal
import sys
import time

import pymultimonaprs

from pymultimonaprs import beacon

__author__ = 'Dominik Heidler <dominik@heidler.eu>'
__copyright__ = 'Copyright 2016 Dominik Heidler'
__license__ = 'GNU General Public License, Version 3'


def beacon_loop(igate, beacon_config):
    bcargs = {
        'lat': float(beacon_config['lat']),
        'lng': float(beacon_config['lng']),
        'callsign': igate.callsign,
        'table': beacon_config['table'],
        'symbol': beacon_config['symbol'],
        'comment': beacon_config['comment'],
        'ambiguity': beacon_config.get('ambiguity', 0),
    }

    bcargs_status = {
        'callsign': igate.callsign,
        'status': beacon_config['status'],
    }

    bcargs_weather = {
        'callsign': igate.callsign,
        'weather': beacon_config['weather'],
    }

    while 1:
        # Position
        frame = beacon.get_beacon_frame(**bcargs)
        if frame:
            igate.send(frame)

        # Status
        frame = beacon.get_status_frame(**bcargs_status)
        if frame:
            igate.send(frame)

        # Weather
        frame = beacon.get_weather_frame(**bcargs_weather)
        if frame:
            igate.send(frame)

        time.sleep(beacon_config['send_every'])


def main():
    parser = argparse.ArgumentParser(description='pymultimonaprs.')
    parser.add_argument(
        '-c', dest='config',
        default='pymultimonaprs.json',
        help='Use this config file')
    parser.add_argument('--syslog', action='store_true', help='Log to syslog')
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Log all traffic - including beacon')
    args = parser.parse_args()

    with open(args.config) as config_file:
        config = json.load(config_file)

    logger = logging.getLogger('pymultimonaprs')
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    logger.setLevel(loglevel)

    if args.syslog:
        loghandler = logging.handlers.SysLogHandler(address='/dev/log')
        formater = logging.Formatter('pymultimonaprs: %(message)s')
        loghandler.setFormatter(formater)
    else:
        loghandler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)+8s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
        loghandler.setFormatter(formatter)
    logger.addHandler(loghandler)

    def mmcb(tnc2_frame):
        try:
            frame = pymultimonaprs.APRSFrame()
            frame.import_tnc2(tnc2_frame)
            if bool(config.get('append_callsign')):
                frame.path.extend([u'qAR', config['callsign']])

            # Filter packets from TCP2RF gateways
            reject_paths = set(['TCPIP', 'TCPIP*', 'NOGATE', 'RFONLY'])
            # '}' is the Third-Party Data Type Identifier (used to encapsulate
            # pkgs) indicating traffic from the internet
            if (len(reject_paths.intersection(frame.path)) > 0 or
                    frame.payload.startswith('}')):
                logger.debug('Rejected: %s', frame.export(False))
            else:
                igate.send(frame)

        except pymultimonaprs.InvalidFrame:
            logger.info('Invalid Frame Received.')
            pass

    logger.info('Starting pymultimonaprs')

    igate = pymultimonaprs.IGate(
        config['callsign'],
        config['passcode'],
        config['gateway'],
        config.get('preferred_protocol', 'any')
    )

    multimon = pymultimonaprs.Multimon(mmcb, config)

    def signal_handler(signal, frame):
        logger.info('Stopping pymultimonaprs')
        igate.exit()
        multimon.exit()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if config.get('beacon') is not None:
        beacon_loop(igate, config['beacon'])


if __name__ == '__main__':
    main()
