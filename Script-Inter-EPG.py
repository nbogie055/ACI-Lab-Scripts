#!/usr/bin/env python
import argparse
import requests
import cobra.mit.access
import cobra.mit.session
import cobra.mit.request
import cobra.model.pol
import cobra.model.fv
import cobra.model.vz
from credentials import *


#Variables and user input for tenant description
NAME = input("Enter your name or ID:\n")
TENANT = "script-inter-epg"
AP1 = "AP-Inter-EPG"
VRF1 = "VRF-internal"
BD1 = "BD_Client"
EPG1 = "EPG_Client"
BD2 = "BD_Server"
EPG2 = "EPG_Server"
GW1 = "192.168.0.1/24"
GW2 = "172.31.0.1/24"
PRIVATE = "private"
VMDOMAIN = "uni/vmmp-VMware/dom-shared-DVS"



def test_tenant(tenant_name, apic_session):
    """
    This function tests if the desired Tenant name is already in use.
    If the name is already in use, it will exit the script early.

    :param tenant_name: The new Tenant's name
    :param apic_session: An established session with the APIC
    """
    # build query for existing tenants
    tenant_query = cobra.mit.request.ClassQuery('fvTenant')
    tenant_query.propFilter = 'eq(fvTenant.name, "{}")'.format(tenant_name)

    # test for truthiness
    if apic_session.query(tenant_query):
        print("\nTenant {} is already created on the APIC\n".format(tenant_name))
        exit(1)


def main():
    """
    This function creates the new Tenant with a VRF, Bridge Domain and Subnet.
    """
    # create a session and define the root
    requests.packages.urllib3.disable_warnings()
    auth = cobra.mit.session.LoginSession(URL, USER, PASS)
    session = cobra.mit.access.MoDirectory(auth)
    session.login()

    root = cobra.model.pol.Uni('')

    # test if tenant name is already in use
    test_tenant(TENANT, session)

    # Create Tenant
    tenant = cobra.model.fv.Tenant(root, name=TENANT, descr=NAME)

    #Create VRF
    vrf = cobra.model.fv.Ctx(tenant, name=VRF1)

    #Create AP
    app_profile = cobra.model.fv.Ap(tenant, name=AP1)

    #Create Contract and Filter
    filter = cobra.model.vz.Filter(tenant, name="Server-Traffic")
    entry = cobra.model.vz.Entry(filter, name="HTTPS", etherT="ip", prot="tcp", dFromPort=443, dToPort=443)
    entry = cobra.model.vz.Entry(filter, name="SSH", etherT="ip", prot="tcp", dFromPort=22, dToPort=22)
    entry = cobra.model.vz.Entry(filter, name="SSH", etherT="ip", prot="icmp")
    contract = cobra.model.vz.BrCP(tenant, name="Inter-EPG")
    subject = cobra.model.vz.Subj(contract, name="Server-Subject")
    associate_filter = cobra.model.vz.RsSubjFiltAtt(subject, tnVzFilterName="Server-Traffic")

    #Create Client BD
    bridge_domain = cobra.model.fv.BD(tenant, name=BD1)
    attach_vrf = cobra.model.fv.RsCtx(bridge_domain, tnFvCtxName=VRF1)
    subnet = cobra.model.fv.Subnet(bridge_domain, ip=GW1, scope=PRIVATE)

    #Create CLient EPG
    endpoint_group = cobra.model.fv.AEPg(app_profile, name=EPG1)
    attach_bd = cobra.model.fv.RsBd(endpoint_group, tnFvBDName=BD1)
    attach_domain = cobra.model.fv.RsDomAtt(endpoint_group, tDn=VMDOMAIN, resImedcy="pre-provision")
    create_lag = cobra.model.fv.AEPgLagPolAtt(attach_domain)
    attach_lag = cobra.model.fv.RsVmmVSwitchEnhancedLagPol(create_lag, tDn="uni/vmmp-VMware/dom-shared-DVS/vswitchpolcont/enlacplagp-active")
    associate_contract = cobra.model.fv.RsCons(endpoint_group, tnVzBrCPName="Inter-EPG")

    #Create Server BD
    bridge_domain = cobra.model.fv.BD(tenant, name=BD2)
    attach_vrf = cobra.model.fv.RsCtx(bridge_domain, tnFvCtxName=VRF1)
    subnet2 = cobra.model.fv.Subnet(bridge_domain, ip=GW2, scope=PRIVATE)

    #Create Server EPG
    endpoint_group = cobra.model.fv.AEPg(app_profile, name=EPG2)
    attach_bd = cobra.model.fv.RsBd(endpoint_group, tnFvBDName=BD2)
    attach_domain = cobra.model.fv.RsDomAtt(endpoint_group, tDn=VMDOMAIN, resImedcy="pre-provision")
    associate_contract = cobra.model.fv.RsProv(endpoint_group, tnVzBrCPName="Inter-EPG")


    #submit the configuration to the apic and print a success message
    config_request = cobra.mit.request.ConfigRequest()
    config_request.addMo(tenant)
    session.commit(config_request)

    print("\nNew Tenant, {}, has been created.\n\nSource:\nVM: Script-Inter-EPG-Client\nIP: 192.168.0.10\nNode: Pod1 Leaf 101/103\n\nDestination:\nVM: Script-Inter-EPG-Server1\nIP: 172.31.0.10\nNode: Pod2 Leaf 205\nVM: Script-Inter-EPG-Server2\nIP: 172.31.0.11\nNode: Pod1 Leaf 102\n".format(TENANT))
    #remove below comment for full tenant json config
    #print("\n{}\n".format(config_request.data))

if __name__ == '__main__':
    main()