import unittest
from enos.utils.extra import *

class TestExtra(unittest.TestCase):
    def test_expand_groups(self):
        grps = "grp[1-3]"
        expanded = expand_groups(grps)
        self.assertEquals(3, len(expanded))
        
    def test_expand_one_group(self):
        grps = "grp"
        expanded = expand_groups(grps)
        self.assertEquals(1, len(expanded))

    def test_expand_groups_with_weird_name(self):
        grps = "a&![,[1-3]"
        expanded = expand_groups(grps)
        self.assertEquals(3, len(expanded))

if __name__ == '__main__':
    unittest.main()

