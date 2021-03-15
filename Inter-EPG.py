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
TENANT = "0Script_TEST"
AP1 = "AP-inter-EPG"
VRF1 = "VRF-internal"
BD1 = "BD_Client"
EPG1 = "EPG_Client"
BD2 = "BD_Server"
EPG2 = "EPG_Server"
GW1 = "192.168.0.1/24"
GW2 = "172.32.0.1/24"
PRIVATE = "private"
VMDOMAIN = "shared-DVS"



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
    entry1 = cobra.model.vz.Entry(filter, name="HTTPS", etherT="ip", prot="tcp", dFromPort=443, dToPort=443)
    entry2 = cobra.model.vz.Entry(filter, name="SSH", etherT="ip", prot="tcp", dFromPort=22, dToPort=22)
    contract = cobra.model.vz.BrCP(tenant, name="Inter-EPG")
    subject = cobra.model.vz.Subj(contract, name="Server-Subject")
    associate_filter = cobra.model.vz.RsSubjFiltAtt(subject, tnVzFilterName="Server-Traffic")

    #Create Client BD
    bridge_domain1 = cobra.model.fv.BD(tenant, name=BD1)
    attach_vrf1 = cobra.model.fv.RsCtx(bridge_domain1, tnFvCtxName=VRF1)
    subnet1 = cobra.model.fv.Subnet(bridge_domain1, ip=GW1, scope=PRIVATE)

    #Create CLient EPG
    endpoint_group1 = cobra.model.fv.AEPg(app_profile, name=EPG1)
    attach_bd1 = cobra.model.fv.RsBd(endpoint_group1, tnFvBDName=BD1)
    attach_domain1 = cobra.model.fv.RsDomAtt(endpoint_group1, tDn="uni/vmmp-VMware/dom-shared-DVS", resImedcy="pre-provision")

    #Create Server BD
    bridge_domain2 = cobra.model.fv.BD(tenant, name=BD2)
    attach_vrf2 = cobra.model.fv.RsCtx(bridge_domain2, tnFvCtxName=VRF1)
    subnet2 = cobra.model.fv.Subnet(bridge_domain2, ip=GW2, scope=PRIVATE)

    #Create Server EPG
    endpoint_group2 = cobra.model.fv.AEPg(app_profile, name=EPG2)
    attach_bd2 = cobra.model.fv.RsBd(endpoint_group2, tnFvBDName=BD2)
    attach_domain2 = cobra.model.fv.RsDomAtt(endpoint_group2, tDn="uni/vmmp-VMware/dom-shared-DVS", resImedcy="pre-provision")


    #submit the configuration to the apic and print a success message
    config_request = cobra.mit.request.ConfigRequest()
    config_request.addMo(tenant)
    session.commit(config_request)

    print("\nNew Tenant, {}, has been created:\n\n{}\n".format(TENANT, config_request.data))


if __name__ == '__main__':
    main()