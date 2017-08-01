import unittest
from enos.utils.network_constraints import *
from enos.provider.host import Host

class TestExpandDescription(unittest.TestCase):

    def test_no_expansion(self):
        desc = {
            'src': 'grp1',
            'dst': 'grp2',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        descs = expand_description(desc)
        self.assertEquals(1, len(descs))
        self.assertDictEqual(desc, descs[0])

    def test_src_expansion(self):
        desc = {
            'src': 'grp[1-3]',
            'dst': 'grp4',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        # checking cardinality : the cartesian product
        descs = expand_description(desc)
        self.assertEquals(3, len(descs))

        # checking that expansion has been generated
        srcs = map(lambda d: d.pop('src'), descs)
        self.assertEquals(set(srcs), {'grp1', 'grp2', 'grp3'})

        # checking that the remaining is untouched
        desc.pop('src')
        for d in descs:
            self.assertDictEqual(desc, d)


    def test_dst_expansion(self):
        desc = {
            'src': 'grp4',
            'dst': 'grp[1-3]',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        # checking cardinality : the cartesian product
        descs = expand_description(desc)
        self.assertEquals(3, len(descs))

        # checking that expansion has been generated
        dsts = map(lambda d: d.pop('dst'), descs)
        self.assertEquals(set(dsts), {'grp1', 'grp2', 'grp3'})

        # checking that the remaining is untouched
        desc.pop('dst')
        for d in descs:
            self.assertDictEqual(desc, d)


    def test_both_expansion(self):
        desc = {
            'src': 'grp[1-3]',
            'dst': 'grp[4-6]',
            'delay': 0,
            'rate': 0,
            'symetric': True
        }
        # checking cardinality : the cartesian product
        descs = expand_description(desc)
        self.assertEquals(9, len(descs))

        # checking that expansion has been generated
        dsts = map(lambda d: d.pop('dst'), descs)
        self.assertEquals(set(dsts), {'grp4', 'grp5', 'grp6'})
        # checking that expansion has been generated
        srcs = map(lambda d: d.pop('src'), descs)
        self.assertEquals(set(srcs), {'grp1', 'grp2', 'grp3'})

        # checking that the remaining is untouched
        desc.pop('dst')
        desc.pop('src')
        for d in descs:
            self.assertDictEqual(desc, d)

class TestGenerateDefaultGrpConstraitns(unittest.TestCase):

    def test_no_expansion(self):
        topology = {
                'grp1': {},
                'grp2': {}
         }
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms'
        }
        descs = generate_default_grp_constraints(topology, network_constraints)

        # Cartesian product is applied
        self.assertEquals(2, len(descs))

        # defaults are applied
        for d in descs:
            self.assertEquals('10mbit', d['rate'])
            self.assertEquals('10ms', d['delay'])

        # descs are symetrics
        self.assertEquals(descs[0]['src'], descs[1]['dst'])
        self.assertEquals(descs[0]['dst'], descs[1]['src'])

    def test_with_expansion(self):
        topology = {
                'grp[1-3]': {},
                'grp[4-6]': {}
         }
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms'
        }
        descs = generate_default_grp_constraints(topology, network_constraints)

        # Cartesian product is applied
        self.assertEquals(6*5, len(descs))

        # defaults are applied
        for d in descs:
            self.assertEquals('10mbit', d['rate'])
            self.assertEquals('10ms', d['delay'])

    def test_except_one_group(self):
        topology = {
                'grp[1-3]': {},
                'grp[4-6]': {}
         }
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'except': ['grp1']
        }
        descs = generate_default_grp_constraints(topology, network_constraints)

        # Cartesian product is applied but grp1 isn't taken
        self.assertEquals(5*4, len(descs))

        for d in descs:
            self.assertTrue('grp1' != d['src'])
            self.assertTrue('grp1' != d['dst'])


class TestGenerateActualGrpConstraints(unittest.TestCase):

    def test_no_expansion_no_symetric(self):
        constraints = [{
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
            'delay': '20ms'
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = generate_actual_grp_constraints(network_constraints)

        self.assertEquals(1, len(descs))
        self.assertDictEqual(constraints[0], descs[0])


    def test_no_expansion_symetric(self):
        constraints = [{
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
            'delay': '20ms',
            'symetric': True
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = generate_actual_grp_constraints(network_constraints)

        self.assertEquals(2, len(descs))

        # bw/rate are applied
        for d in descs:
            self.assertEquals('20mbit', d['rate'])
            self.assertEquals('20ms', d['delay'])

        # descs are symetrics
        self.assertEquals(descs[0]['src'], descs[1]['dst'])
        self.assertEquals(descs[0]['dst'], descs[1]['src'])

    def test_expansion_symetric(self):
        constraints = [{
            'src': 'grp[1-3]',
            'dst': 'grp[4-6]',
            'rate': '20mbit',
            'delay': '20ms',
            'symetric': True
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = generate_actual_grp_constraints(network_constraints)

        self.assertEquals(3*3*2, len(descs))

        # bw/rate are applied
        for d in descs:
            self.assertEquals('20mbit', d['rate'])
            self.assertEquals('20ms', d['delay'])

    def test_expansion_no_symetric(self):
        constraints = [{
            'src': 'grp[1-3]',
            'dst': 'grp[4-6]',
            'rate': '20mbit',
            'delay': '20ms',
            }]
        network_constraints = {
            'default_rate': '10mbit',
            'default_delay': '10ms',
            'constraints' : constraints
        }
        descs = generate_actual_grp_constraints(network_constraints)

        self.assertEquals(3*3, len(descs))

        # bw/rate are applied
        for d in descs:
            self.assertEquals('20mbit', d['rate'])
            self.assertEquals('20ms', d['delay'])

class TestMergeConstraints(unittest.TestCase):

    def test_merge_constraints(self):
        constraint = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '10mbit',
            'delay': '10ms'
        }
        constraints = [constraint]
        override = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
            'delay': '20ms'
        }
        overrides = [override]
        merge_constraints(constraints, overrides)
        self.assertDictEqual(override, constraints[0])

    def test_merge_constraints_default(self):
        constraint = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '10mbit',
            'delay': '10ms'
        }
        constraints = [constraint]
        override = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '20mbit',
        }
        overrides = [override]
        merged = merge_constraints(constraints, overrides)

        override.update({'delay': '10ms'})
        self.assertDictEqual(override, constraints[0])

class TestBuildIpConstraints(unittest.TestCase):

    def test_build_ip_constraints(self):
        # role distribution
        rsc = {
            'grp1': [Host('node1')],
            'grp2': [Host('node2')]
        }
        # ips informations
        ips = {
            'node1': {
                'all_ipv4_addresses': ['ip11', 'ip12'],
                'devices': [{'device': 'eth0', 'active': True},{'device': 'eth1', 'active': True}]
             },
            'node2': {
                'all_ipv4_addresses': ['ip21', 'ip21'],
                'devices': [{'device': 'eth0', 'active': True},{'device': 'eth1', 'active': True}]
             }
        }
        # the constraints
        constraint = {
            'src': 'grp1',
            'dst': 'grp2',
            'rate': '10mbit',
            'delay': '10ms',
            'loss': '0.1%'
        }
        constraints = [constraint]

        ips_with_tc = build_ip_constraints(rsc, ips, constraints)
        # tc rules are applied on the source only
        self.assertTrue('tc' in ips_with_tc['node1'])
        tcs = ips_with_tc['node1']['tc']
        # one rule per dest ip and source device
        self.assertEquals(2*2, len(tcs))


if __name__ == '__main__':
    unittest.main()
