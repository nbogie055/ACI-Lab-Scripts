#!/usr/bin/env python
import argparse
import requests
import cobra.mit.access
import cobra.mit.session
import cobra.mit.request
import cobra.model.pol
import cobra.model.fv
import cobra.model.vz
import cobra.model.vns
from credentials import *


#Variables and user input for tenant description
NAME = input("Enter your name or ID:\n")
TENANT = "Script-mpod-pbr"
AP1 = "AP-PBR"
VRF1 = "VRF-internal"
#Client
BD1 = "BD_Client"
GW1 = "192.168.0.1/24"
EPG1 = "EPG_Client"
#Server
BD2 = "BD_Server"
GW2 = "172.31.0.1/24"
EPG2 = "EPG_Server"
#Firewall
BDINSIDE = "BD_ASA_Inside"
GW3 = "10.0.10.1/25"
BDOUTSIDE = "BD_ASA_Outside"
GW4 = "10.0.10.129/25"

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
    This function creates all tenant related policies for a pbr deployment
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
    contract = cobra.model.vz.BrCP(tenant, name="PBR-CT")
    subject = cobra.model.vz.Subj(contract, name="Server-Subject")
    associate_filter = cobra.model.vz.RsSubjFiltAtt(subject, tnVzFilterName="Server-Traffic")

    #Create Client BD
    bridge_domain = cobra.model.fv.BD(tenant, name=BD1)
    attach_vrf = cobra.model.fv.RsCtx(bridge_domain, tnFvCtxName=VRF1)
    subnet = cobra.model.fv.Subnet(bridge_domain, ip=GW1, scope=PRIVATE)

    #Create CLient EPG
    endpoint_group = cobra.model.fv.AEPg(app_profile, name=EPG1)
    attach_bd = cobra.model.fv.RsBd(endpoint_group, tnFvBDName=BD1)
    attach_domain = cobra.model.fv.RsDomAtt(endpoint_group, tDn="uni/vmmp-VMware/dom-shared-DVS", resImedcy="pre-provision")
    associate_contract = cobra.model.fv.RsCons(endpoint_group, tnVzBrCPName="PBR-CT")

    #Create Server BD
    bridge_domain = cobra.model.fv.BD(tenant, name=BD2)
    attach_vrf = cobra.model.fv.RsCtx(bridge_domain, tnFvCtxName=VRF1)
    subnet = cobra.model.fv.Subnet(bridge_domain, ip=GW2, scope=PRIVATE)

    #Create Server EPG
    endpoint_group = cobra.model.fv.AEPg(app_profile, name=EPG2)
    attach_bd = cobra.model.fv.RsBd(endpoint_group, tnFvBDName=BD2)
    attach_domain = cobra.model.fv.RsDomAtt(endpoint_group, tDn="uni/vmmp-VMware/dom-shared-DVS", resImedcy="pre-provision")
    create_lag = cobra.model.fv.AEPgLagPolAtt(attach_domain)
    attach_lag = cobra.model.fv.RsVmmVSwitchEnhancedLagPol(create_lag, tDn="uni/vmmp-VMware/dom-shared-DVS/vswitchpolcont/enlacplagp-active")
    associate_contract = cobra.model.fv.RsProv(endpoint_group, tnVzBrCPName="PBR-CT")

    #Create inside Firewall BD
    bridge_domain = cobra.model.fv.BD(tenant, name=BDINSIDE, unkMacUcastAct="flood", arpFlood="yes")
    attach_vrf = cobra.model.fv.RsCtx(bridge_domain, tnFvCtxName=VRF1)
    subnet = cobra.model.fv.Subnet(bridge_domain, ip=GW3, scope=PRIVATE)

    #Create outside Firewall BD
    bridge_domain = cobra.model.fv.BD(tenant, name=BDOUTSIDE, unkMacUcastAct="flood", arpFlood="yes")
    attach_vrf = cobra.model.fv.RsCtx(bridge_domain, tnFvCtxName=VRF1)
    subnet = cobra.model.fv.Subnet(bridge_domain, ip=GW4, scope=PRIVATE)

    #Create inside Redirect polic
    redir_policy = cobra.model.vns.SvcCont(tenant)
    redir_inside = cobra.model.vns.SvcRedirectPol(redir_policy, name="inside", destType="L3")
    inside_dest = cobra.model.vns.RedirectDest(redir_inside, ip="10.0.10.2", mac="00:50:56:a8:92:d6")

    #Create outside Redirect policy
    redir_outside = cobra.model.vns.SvcRedirectPol(redir_policy, name="outside", destType="L3")
    outside_dest = cobra.model.vns.RedirectDest(redir_outside, ip="10.0.10.130", mac="00:50:56:a8:a5:61")

    #Create L4 device
    l4_device = cobra.model.vns.LDevVip(tenant, name="ASAV", managed="no", devtype="VIRTUAL", svcType="FW")
    attach_domain = cobra.model.vns.RsALDevToDomP(l4_device, tDn="uni/vmmp-VMware/dom-shared-DVS")
    add_device = cobra.model.vns.CDev(l4_device, name="ASAv-1", vcenterName="shared-vc", vmName="Script-pbr-ASAV")

    #Create inside interface
    inside_if = cobra.model.vns.CIf(add_device, name="inside", vnicName="Network adapter 2")
    inside_path = cobra.model.vns.RsCIfPathAtt(inside_if, tDn="topology/pod-1/paths-102/pathep-[eth1/43]")

    #Create inside interface
    outside_if = cobra.model.vns.CIf(add_device, name="outside", vnicName="Network adapter 3")
    outside_path = cobra.model.vns.RsCIfPathAtt(outside_if, tDn="topology/pod-1/paths-102/pathep-[eth1/43]")

    #Create inside cluster interface
    inside_cluster = cobra.model.vns.LIf(l4_device, name="inside")
    attach_inif = cobra.model.vns.RsCIfAttN(inside_cluster, tDn="uni/tn-Script-mpod-pbr/lDevVip-ASAV/cDev-ASAv-1/cIf-[inside]")
    
    #Create outside cluster interface
    outside_cluster = cobra.model.vns.LIf(l4_device, name="outside")
    attach_outif = cobra.model.vns.RsCIfAttN(outside_cluster, tDn="uni/tn-Script-mpod-pbr/lDevVip-ASAV/cDev-ASAv-1/cIf-[outside]")

    #Create Service Graph
    service_graph = cobra.model.vns.AbsGraph(tenant, name="epg-SG")
    service_type = cobra.model.vns.AbsNode(service_graph, name="N1", funcTemplateType="FW_ROUTED", routingMode="Redirect", funcType="GoTo", managed="no")
    attach_ldev = cobra.model.vns.RsNodeToLDev(service_type, tDn="uni/tn-Script-mpod-pbr/lDevVip-ASAV")
    #Create Consumer and Provider
    consumer_func = cobra.model.vns.AbsFuncConn(service_type, name="consumer")
    provider_func = cobra.model.vns.AbsFuncConn(service_type, name="provider")
    #create connectors
    connector1 = cobra.model.vns.AbsConnection(service_graph, name="C1", adjType="L3", connDir="provider", connType="external")
    connector2 = cobra.model.vns.AbsConnection(service_graph, name="C2", adjType="L3", connDir="provider", connType="external")
    #Create Terminal nodes
    term_nodecon = cobra.model.vns.AbsTermNodeCon(service_graph, name="T1")
    term_con = cobra.model.vns.AbsTermConn(term_nodecon, name="1")
    term_nodeprov = cobra.model.vns.AbsTermNodeProv(service_graph, name="T2")
    term_con1 = cobra.model.vns.AbsTermConn(term_nodeprov, name="1")

    #attach terminal nodes to connectors
    attach_con1 = cobra.model.vns.RsAbsConnectionConns(connector1, tDn="uni/tn-Script-mpod-pbr/AbsGraph-epg-SG/AbsTermNodeCon-T1/AbsTConn")
    attach_nodcon = cobra.model.vns.RsAbsConnectionConns(connector1, tDn="uni/tn-Script-mpod-pbr/AbsGraph-epg-SG/AbsNode-N1/AbsFConn-consumer")
    attach_con2 = cobra.model.vns.RsAbsConnectionConns(connector2, tDn="uni/tn-Script-mpod-pbr/AbsGraph-epg-SG/AbsTermNodeProv-T2/AbsTConn")
    attach_nodprov = cobra.model.vns.RsAbsConnectionConns(connector2, tDn="uni/tn-Script-mpod-pbr/AbsGraph-epg-SG/AbsNode-N1/AbsFConn-provider")


    #Add service graph to contract
    #attach_ct = cobra.model.vns.RtSubjGraphAtt(service_graph, tDn="uni/tn-Script-mpod-pbr/brc-PBR-CT/subj-Server-Subject")
    attach_sg = cobra.model.vz.RsSubjGraphAtt(subject, tnVnsAbsGraphName="epg-SG")

    #Create device selection policy
    dev_policy = cobra.model.vns.LDevCtx(tenant, ctrctNameOrLbl="PBR-CT", graphNameOrLbl="epg-SG", nodeNameOrLbl="N1")
    attach_device = cobra.model.vns.RsLDevCtxToLDev(dev_policy, tDn="uni/tn-Script-mpod-pbr/lDevVip-ASAV")

    #Create consumer and provider interface context
    consumer_ctx = cobra.model.vns.LIfCtx(dev_policy, connNameOrLbl="consumer", L3Dest="yes")
    attach_inside_bd = cobra.model.vns.RsLIfCtxToBD(consumer_ctx, tDn="uni/tn-Script-mpod-pbr/BD-BD_ASA_Inside")
    attach_inside_if = cobra.model.vns.RsLIfCtxToLIf(consumer_ctx, tDn="uni/tn-Script-mpod-pbr/lDevVip-ASAV/lIf-inside")
    attach_inside_redir = cobra.model.vns.RsLIfCtxToSvcRedirectPol(consumer_ctx, tDn="uni/tn-Script-mpod-pbr/svcCont/svcRedirectPol-inside")

    provider_ctx = cobra.model.vns.LIfCtx(dev_policy, connNameOrLbl="provider", L3Dest="yes")
    attach_outside_bd = cobra.model.vns.RsLIfCtxToBD(provider_ctx, tDn="uni/tn-Script-mpod-pbr/BD-BD_ASA_Outside")
    attach_outside_if = cobra.model.vns.RsLIfCtxToLIf(provider_ctx, tDn="uni/tn-Script-mpod-pbr/lDevVip-ASAV/lIf-outside")
    attach_outside_redir = cobra.model.vns.RsLIfCtxToSvcRedirectPol(provider_ctx, tDn="uni/tn-Script-mpod-pbr/svcCont/svcRedirectPol-outside")

    #submit the configuration to the apic and print a success message
    config_request = cobra.mit.request.ConfigRequest()
    config_request.addMo(tenant)
    session.commit(config_request)

    print("\nNew Tenant, {}, has been created.\n".format(TENANT))
    #remove below comment for full tenant json config
    #print("\n{}\n".format(config_request.data))


if __name__ == '__main__':
    main()