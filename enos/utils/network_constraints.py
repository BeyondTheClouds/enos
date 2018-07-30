import copy
from .extra import expand_groups


def expand_description(desc):
    """Expand the description given the group names/patterns
    e.g:
    {src: grp[1-3], dst: grp[4-6] ...} will generate 9 descriptions
    """
    srcs = expand_groups(desc['src'])
    dsts = expand_groups(desc['dst'])
    descs = []
    for src in srcs:
        for dst in dsts:
            local_desc = desc.copy()
            local_desc['src'] = src
            local_desc['dst'] = dst
            descs.append(local_desc)

    return descs


def same(g1, g2):
    """Two network constraints are equals if they have the same
    sources and destinations
    """
    return g1['src'] == g2['src'] and g1['dst'] == g2['dst']


def generate_default_grp_constraints(topology, network_constraints):
    """Generate default symetric grp constraints.
    """
    default_delay = network_constraints.get('default_delay')
    default_rate = network_constraints.get('default_rate')
    default_loss = network_constraints.get('default_loss')
    except_groups = network_constraints.get('except', [])
    # expand each groups
    grps = map(lambda g: expand_groups(g), topology.keys())
    # flatten
    grps = [x for expanded_group in grps for x in expanded_group]
    # building the default group constraints
    return [{
            'src': grp1,
            'dst': grp2,
            'delay': default_delay,
            'rate': default_rate,
            'loss': default_loss
        } for grp1 in grps for grp2 in grps
        if grp1 != grp2 and grp1 not in except_groups and
            grp2 not in except_groups]


def generate_actual_grp_constraints(network_constraints):
    """Generate the user specified constraints
    """
    if 'constraints' not in network_constraints:
        return []

    constraints = network_constraints['constraints']
    actual = []
    for desc in constraints:
        descs = expand_description(desc)
        for desc in descs:
            actual.append(desc)
            if 'symetric' in desc:
                sym = desc.copy()
                sym['src'] = desc['dst']
                sym['dst'] = desc['src']
                actual.append(sym)
    return actual


def merge_constraints(constraints, overrides):
    """Merge the constraints avoiding duplicates
    Change constraints in place.
    """
    for o in overrides:
        i = 0
        while i < len(constraints):
            c = constraints[i]
            if same(o, c):
                constraints[i].update(o)
                break
            i = i + 1


def build_grp_constraints(topology, network_constraints):
    """Generate constraints at the group level,
    It expands the group names and deal with symetric constraints.
    """
    # generate defaults constraints
    constraints = generate_default_grp_constraints(topology,
                                                   network_constraints)
    # Updating the constraints if necessary
    if 'constraints' in network_constraints:
        actual = generate_actual_grp_constraints(network_constraints)
        merge_constraints(constraints, actual)

    return constraints


def build_ip_constraints(rsc, ips, constraints):
    """Generate the constraints at the ip/device level.
    Those constraints are those used by ansible to enforce tc/netem rules.
    """
    local_ips = copy.deepcopy(ips)
    for constraint in constraints:
        gsrc = constraint['src']
        gdst = constraint['dst']
        gdelay = constraint['delay']
        grate = constraint['rate']
        gloss = constraint['loss']
        for s in rsc[gsrc]:
            # one possible source
            # Get all the active devices for this source
            active_devices = filter(lambda x: x["active"],
                                    local_ips[s.alias]['devices'])
            # Get only the name of the active devices
            sdevices = map(lambda x: x['device'], active_devices)
            for sdevice in sdevices:
                # one possible device
                for d in rsc[gdst]:
                    # one possible destination
                    dallips = local_ips[d.alias]['all_ipv4_addresses']
                    # Let's keep docker bridge out of this
                    dallips = filter(lambda x: x != '172.17.0.1', dallips)
                    for dip in dallips:
                        local_ips[s.alias].setdefault('tc', []).append({
                            'source': s.alias,
                            'target': dip,
                            'device': sdevice,
                            'delay': gdelay,
                            'rate': grate,
                            'loss': gloss
                        })
    return local_ips
