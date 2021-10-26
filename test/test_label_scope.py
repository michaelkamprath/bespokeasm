import unittest
import importlib.resources as pkg_resources

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType

class TestLabelScope(unittest.TestCase):

    def test_single_layer_scope(self):
        ls1 = LabelScope(LabelScopeType.GLOBAL, None, 'test')

        ls1.set_label_value('test1', 12, 777)
        ls1.set_label_value('test2', 42, 888)

        self.assertEqual(ls1.get_label_value('test1'), 12)
        self.assertEqual(ls1.get_label_value('test2'), 42)
        self.assertIsNone(ls1.get_label_value('undef'), 'should not find undefined label')

        with self.assertRaises(SystemExit, msg='label cannot be defined multiple times'):
            ls1.set_label_value('test1', 666, 1234)

    def test_multilayer_scopes(self):
        ls1 = LabelScope(LabelScopeType.GLOBAL, None, 'test')
        ls2 = LabelScope(LabelScopeType.FILE, ls1, 'mycode.py')
        ls3 = LabelScope(LabelScopeType.LOCAL, ls2, 'my_label')
        ls4 = LabelScope(LabelScopeType.LOCAL, ls2, 'your_label')

        ls3.set_label_value('global1', 12, 1)
        ls3.set_label_value('_file1', 24, 2)
        ls3.set_label_value('.local1', 44, 3)
        ls4.set_label_value('global2', 13, 4)
        ls4.set_label_value('_file2', 14, 5)
        ls4.set_label_value('.local2', 88, 6)
        ls2.set_label_value('_file3', 66, 7)

        self.assertEqual(ls3.get_label_value('global1'), 12)
        self.assertEqual(ls2.get_label_value('global1'), 12)
        self.assertEqual(ls1.get_label_value('global1'), 12)

        self.assertEqual(ls3.get_label_value('_file1'), 24)
        self.assertEqual(ls2.get_label_value('_file1'), 24)
        self.assertIsNone(ls1.get_label_value('_file1'), msg='label not at global scope')

        self.assertEqual(ls3.get_label_value('.local1'), 44)
        self.assertIsNone(ls2.get_label_value('.local1'), msg='label not at file scope')
        self.assertIsNone(ls1.get_label_value('.local1'), msg='label not at global scope')
        self.assertIsNone(ls3.get_label_value('.local2'), msg='label not this local scope')

        self.assertEqual(ls4.get_label_value('global1'), 12, 'global value vailable at other locals')
        self.assertEqual(ls4.get_label_value('_file1'), 24, 'file value vailable at other locals')
        self.assertEqual(ls3.get_label_value('_file2'), 14, 'file value vailable at other locals')

