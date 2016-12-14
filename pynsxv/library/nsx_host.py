#!/usr/bin/env python
# coding=utf-8

import ConfigParser
from tabulate import tabulate
from nsxramlclient.client import NsxClient
from libutils import get_hostmoid, connect_to_vc, get_mo_by_inventory_path
from pkg_resources import resource_filename

__author__ = 'YOMOGItaro'


def _communication_status(client_session, moid, **kwargs):
    resp = client_session.read('inventoryStatusHost', uri_parameters={'hostId': moid})
    statuses = resp['body']['hostConnStatus']
    print(tabulate([statuses], headers='keys', tablefmt='psql'))


def _host_main(args):
    if args.debug:
        debug = True
    else:
        debug = False

    config = ConfigParser.ConfigParser()
    assert config.read(args.ini), 'could not read config file {}'.format(args.ini)

    try:
        nsxramlfile = config.get('nsxraml', 'nsxraml_file')
    except (ConfigParser.NoSectionError):
        nsxramlfile_dir = resource_filename(__name__, 'api_spec')
        nsxramlfile = '{}/nsxvapi.raml'.format(nsxramlfile_dir)

    client_session = NsxClient(nsxramlfile, config.get('nsxv', 'nsx_manager'),
                               config.get('nsxv', 'nsx_username'), config.get('nsxv', 'nsx_password'), debug=debug)

    if args.host_inventory_path or args.host_name:
        vccontent = connect_to_vc(config.get('vcenter', 'vcenter'), config.get('vcenter', 'vcenter_user'),
                                  config.get('vcenter', 'vcenter_passwd'))

    if args.host_inventory_path:
        obj = get_mo_by_inventory_path(vccontent, args.host_inventory_path)
        moid = str(obj._moId)
    elif args.host_name:
        moid = get_hostmoid(vccontent, args.host_name)
    else:
        moid = args.host_moid

    try:
        command_selector = {
            'communication_status': _communication_status,
        }
        command_selector[args.command](client_session, verbose=args.verbose,
                                       moid=moid)

    except KeyError as e:
        print('Unknown command {}'.format(e))


def contruct_parser(subparsers):
    parser = subparsers.add_parser('host', description="Working with ESXi host.",
                                   help="Working with ESXi host.")
    parser.add_argument("command", help="""
    communication_status:             Communication Status of a Specific Host
    """)
    moid_detection_group = parser.add_mutually_exclusive_group(required=True)
    moid_detection_group.add_argument("-m",
                                      "--host-moid",
                                      help="host moid. E.g., '--host-moid=host-1'.")
    moid_detection_group.add_argument("-i",
                                      "--host-inventory-path",
                                      help="host inventory full path. E.g., '--host-inventory-path=dc/vm/folder/cluster1/host1'.")
    moid_detection_group.add_argument("-n",
                                      "--host-name",
                                      help="host name. E.g., '--host-name=hostA'.")
    parser.set_defaults(func=_host_main)
