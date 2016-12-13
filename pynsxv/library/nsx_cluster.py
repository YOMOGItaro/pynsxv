#!/usr/bin/env python
# coding=utf-8

import ConfigParser
from tabulate import tabulate
from nsxramlclient.client import NsxClient
from libutils import get_edgeresourcepoolmoid, connect_to_vc, get_mo_by_inventory_path, wait_for_job_completion
from pkg_resources import resource_filename

__author__ = 'YOMOGItaro'


def _is_cluster_prepared(client_session, moid):
    resp = client_session.read('nwfabricStatus', query_parameters_dict={'resource': moid})
    statuses = resp['body']['resourceStatuses']['resourceStatus']['nwFabricFeatureStatus']
    host_prep_status = next((r for r in statuses if r['featureId'] == "com.vmware.vshield.vsm.nwfabric.hostPrep"))

    return host_prep_status['status'] == "GREEN"


def _show_nwfabric_status(client_session, moid, **kwargs):
    resp = client_session.read('nwfabricStatus', query_parameters_dict={'resource': moid})
    statuses = resp['body']['resourceStatuses']['resourceStatus']['nwFabricFeatureStatus']
    print(tabulate(statuses, headers='keys', tablefmt='psql'))


def _install_network_virtualization(client_session, moid, **kwargs):
    if(_is_cluster_prepared(client_session, moid)):
        print("{} is already prepared.".format(moid))
        return
    schema = client_session.extract_resource_body_example('nwfabricConfig', 'create')
    schema['nwFabricFeatureConfig']['resourceConfig']['resourceId'] = moid
    resp = client_session.create('nwfabricConfig', request_body_dict=schema)
    print("preparing {}.".format(moid))
    wait_for_job_completion(client_session=client_session, job_id=resp['objectId'], completion_status='COMPLETED')
    print("cluster {} is prepared.".format(moid))


def _uninstall_network_virtualization(client_session, moid, **kwargs):
    if(not _is_cluster_prepared(client_session, moid)):
        print("{} is already unprepared.".format(moid))
        return
    schema = client_session.extract_resource_body_example('nwfabricConfig', 'delete')
    schema['nwFabricFeatureConfig']['resourceConfig']['resourceId'] = moid
    resp = client_session.delete('nwfabricConfig', request_body_dict=schema)
    print("unpreparing {}.".format(moid))
    wait_for_job_completion(client_session=client_session, job_id=resp['objectId'], completion_status='COMPLETED')
    print("cluster {} is unprepared.".format(moid))


def _cluster_main(args):
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

    if args.cluster_inventory_path or args.cluster_name:
        vccontent = connect_to_vc(config.get('vcenter', 'vcenter'), config.get('vcenter', 'vcenter_user'),
                                  config.get('vcenter', 'vcenter_passwd'))

    if args.cluster_inventory_path:
        obj = get_mo_by_inventory_path(vccontent, args.cluster_inventory_path)
        moid = str(obj._moId)
    elif args.cluster_name:
        moid = get_edgeresourcepoolmoid(vccontent, args.cluster_name)
    else:
        moid = args.cluster_moid

    try:
        command_selector = {
            'show_nwfabric_status': _show_nwfabric_status,
            'install_network_virtualization': _install_network_virtualization,
            'uninstall_network_virtualization': _uninstall_network_virtualization,
        }
        command_selector[args.command](client_session, verbose=args.verbose,
                                       moid=moid)

    except KeyError as e:
        print('Unknown command {}'.format(e))


def contruct_parser(subparsers):
    parser = subparsers.add_parser('cluster', description="Working with Network Virtualization Components and VXLAN.",
                                   help="Working with Network Virtualization Components and VXLAN.")
    parser.add_argument("command", help="""
    show_nwfabric_status:              Retrieve the network fabric status of the specified resource
    install_network_virtualization:   Install Network Virtualization Components
    uninstall_network_virtualization: Uninstall Network Virtualization Components
    """)
    moid_detection_group = parser.add_mutually_exclusive_group(required=True)
    moid_detection_group.add_argument("-m",
                                      "--cluster-moid",
                                      help="cluster moid. E.g., '--cluster-moid=domain-c1'.")
    moid_detection_group.add_argument("-i",
                                      "--cluster-inventory-path",
                                      help="cluster inventory full path. E.g., '--cluster-inventory-path=dc/vm/folder/cluster1'.")
    moid_detection_group.add_argument("-n",
                                      "--cluster-name",
                                      help="cluster name. E.g., '--cluster-name=cluster001'.")
    parser.set_defaults(func=_cluster_main)
