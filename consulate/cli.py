"""Consulate CLI commands"""
# pragma: no cover
import argparse
import json
import sys

from requests import exceptions

import consulate
from consulate import adapters
from consulate import utils


def connection_error():
    """Common exit routine when consulate can't connect to Consul"""
    sys.stderr.write('ERROR: Could not connect to consul\n')
    sys.exit(1)


KV_PARSERS = [
    ('backup', 'Backup to stdout or a JSON file', [
        [['-f', '--file'],
         {'help': 'JSON file to read instead of stdin',
          'nargs': '?'}]]),
    ('restore', 'Restore from stdin or a JSON file', [
        [['-f', '--file'],
         {'help': 'JSON file to read instead of stdin',
          'nargs': '?'}],
        [['-n', '--no-replace'],
         {'help': 'Do not replace existing entries',
          'action': 'store_true'}]]),
    ('ls', 'List all of the keys', [
        [['-l', '--long'],
         {'help': 'Long format',
          'action': 'store_true'}]]),
    ('mkdir', 'Create a folder', [
        [['path'],
         {'help': 'The path to create'}]]),
    ('get', 'Get a key from the database', [
        [['key'],
         {'help': 'The key to get'}]]),
    ('set', 'Set a key in the database', [
        [['key'], {'help': 'The key to set'}],
        [['value'], {'help': 'The value of the key'}]]),
    ('rm', 'Remove a key from the database', [
        [['key'], {'help': 'The key to remove'}],
        [['-r', '--recurse'],
         {'help': 'Delete all keys prefixed with the specified key',
          'action': 'store_true'}]])]


def add_kv_args(parser):
    """Add the kv command and arguments.

    :param argparse.Subparser parser: parser

    """
    kv_parser = parser.add_parser('kv', help='Key/Value Database Utilities')

    subparsers = kv_parser.add_subparsers(dest='action',
                                          title='Key/Value Database Utilities')

    for (name, help_text, arguments) in KV_PARSERS:
        parser = subparsers.add_parser(name, help=help_text)
        for (args, kwargs) in arguments:
            parser.add_argument(*args, **kwargs)


def add_register_args(parser):
    """Add the register command and arguments.

    :param argparse.Subparser parser: parser

    """
    # Service registration
    registerp = parser.add_parser('register',
                                  help='Register a service for this node')
    registerp.add_argument('name', help='The service name')
    registerp.add_argument('-a', '--address', default=None,
                           help='Specify an address')
    registerp.add_argument('-p', '--port', default=None, help='Specify a port')
    registerp.add_argument('-s', '--service-id', default=None,
                           help='Specify a service ID')
    registerp.add_argument('-t', '--tags', default=[],
                           help='Specify a comma delimited list of tags')
    rsparsers = registerp.add_subparsers(dest='ctype',
                                         title='Service Check Options')
    check = rsparsers.add_parser('check',
                                 help='Define an external script-based check')
    check.add_argument('interval', default=10, type=int,
                       help='How often to run the check script')
    check.add_argument('path', default=None,
                       help='Path to the script invoked by Consul')
    rsparsers.add_parser('no-check', help='Do not enable service monitoring')
    ttl = rsparsers.add_parser('ttl', help='Define a duration based TTL check')
    ttl.add_argument('duration', type=int, default=10,
                     help='TTL duration for a service with missing check data')


def parse_cli_args():
    """Create the argument parser and add the arguments"""
    parser = argparse.ArgumentParser(description='CLI utilities for Consul')

    parser.add_argument('--api-scheme',
                        default='http',
                        help='The scheme to use for connecting to Consul with')
    parser.add_argument('--api-host',
                        default='localhost',
                        help='The consul host to connect on')
    parser.add_argument('--api-port',
                        default=8500,
                        help='The consul API port to connect to')
    parser.add_argument('--datacenter',
                        dest='dc',
                        default=None,
                        help='The datacenter to specify for the connection')
    parser.add_argument('--token', default=None, help='ACL token')

    sparser = parser.add_subparsers(title='Commands', dest='command')
    add_register_args(sparser)
    add_kv_args(sparser)
    return parser.parse_args()


def kv_backup(consul, args):
    """Backup the Consul KV database

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    handle = open(args.file, 'w') if args.file else sys.stdout
    try:
        handle.write(json.dumps(consul.kv.records()) + '\n')
    except exceptions.ConnectionError:
        connection_error()


def kv_delete(consul, args):
    """Remove a key from the Consulate database

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    try:
        del consul.kv[args.key]
    except exceptions.ConnectionError:
        connection_error()


def kv_get(consul, args):
    """Get the value of a key from the Consul database

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    try:
        sys.stdout.write("%s\n" % consul.kv.get(args.key))
    except exceptions.ConnectionError:
        connection_error()


def kv_ls(consul, args):
    """List out the keys from the Consul KV database

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    try:
        for key in consul.kv.keys():
            if args.long:
                print('{0:>14} {1}'.format(len(consul.kv[key]), key))
            else:
                print(key)
    except exceptions.ConnectionError:
        connection_error()


def kv_mkdir(consul, args):
    """Make a key based path/directory in the KV database

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    if not args.path[:-1] == '/':
        args.path += '/'
    try:
        consul.kv.set(args.path, None)
    except exceptions.ConnectionError:
        connection_error()


def kv_restore(consul, args):
    """Restore the Consul KV store

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    handle = open(args.file, 'r') if args.file else sys.stdin
    data = json.load(handle)
    for row in data:
        # Here's an awesome thing to make things work
        if not utils.PYTHON3 and isinstance(row[2], unicode):
            row[2] = row[2].encode('utf-8')
        try:
            consul.kv.set_record(row[0], row[1], row[2], not args.no_replace)
        except exceptions.ConnectionError:
            connection_error()


def kv_rm(consul, args):
    """Remove a key from the Consulate database

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    try:
        consul.kv.delete(args.key, args.recurse)
    except exceptions.ConnectionError:
        connection_error()


def kv_set(consul, args):
    """Set a value of a key int the Consul database

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    try:
        consul.kv[args.key] = args.value
    except exceptions.ConnectionError:
        connection_error()


def register(consul, args):
    """Handle service registration.

    :param consulate.api_old.Consul consul: The Consul instance
    :param argparser.namespace args: The cli args

    """
    check = args.path if args.ctype == 'check' else None
    interval = '%ss' % args.interval if args.ctype == 'check' else None
    ttl = '%ss' % args.duration if args.ctype == 'ttl' else None
    tags = args.tags.split(',') if args.tags else None
    try:
        consul.agent.service.register(args.name, args.service_id, args.address,
                                      args.port, tags, check, interval, ttl)
    except exceptions.ConnectionError:
        connection_error()

# Mapping dict to simplify the code in main()
KV_ACTIONS = {
    'backup': kv_backup,
    'del': kv_delete,
    'get': kv_get,
    'ls': kv_ls,
    'mkdir': kv_mkdir,
    'restore': kv_restore,
    'rm': kv_rm,
    'set': kv_set}


def main():
    """Entrypoint for the consulate cli application"""
    args = parse_cli_args()

    adapter = None if args.scheme == 'http+unix' else adapters.UnixSocketRequest
    consul = consulate.Consul(args.api_host, args.api_port, args.dc, args.token,
                              args.scheme, adapter)
    if args.command == 'register':
        register(consul, args)
    elif args.command == 'kv':
        KV_ACTIONS[args.action](consul, args)
