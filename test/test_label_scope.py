import unittest
import importlib.resources as pkg_resources

from bespokeasm.assembler.label_scope import LabelScope, LabelScopeType, GlobalLabelScope

class TestLabelScope(unittest.TestCase):

    def test_single_layer_scope(self):
        ls1 = GlobalLabelScope(set())

        ls1.set_label_value('test1', 12, 777)
        ls1.set_label_value('test2', 42, 888)

        self.assertEqual(ls1.get_label_value('test1', 1), 12)
        self.assertEqual(ls1.get_label_value('test2', 2), 42)
        self.assertIsNone(ls1.get_label_value('undef', 3), 'should not find undefined label')

        with self.assertRaises(SystemExit, msg='label cannot be defined multiple times'):
            ls1.set_label_value('test1', 666, 1234)

    def test_multilayer_scopes(self):
        ls1 = GlobalLabelScope(set())
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

        self.assertEqual(ls3.get_label_value('global1', 1), 12)
        self.assertEqual(ls2.get_label_value('global1', 2), 12)
        self.assertEqual(ls1.get_label_value('global1', 3), 12)

        self.assertEqual(ls3.get_label_value('_file1', 4), 24)
        self.assertEqual(ls2.get_label_value('_file1', 5), 24)
        self.assertIsNone(ls1.get_label_value('_file1', 6), msg='label not at global scope')

        self.assertEqual(ls3.get_label_value('.local1', 7), 44)
        self.assertIsNone(ls2.get_label_value('.local1', 8), msg='label not at file scope')
        self.assertIsNone(ls1.get_label_value('.local1', 9), msg='label not at global scope')
        self.assertIsNone(ls3.get_label_value('.local2', 10), msg='label not this local scope')

        self.assertEqual(ls4.get_label_value('global1', 11), 12, 'global value vailable at other locals')
        self.assertEqual(ls4.get_label_value('_file1', 12), 24, 'file value vailable at other locals')
        self.assertEqual(ls3.get_label_value('_file2', 13), 14, 'file value vailable at other locals')

    def test_register_label_identification(self):
        global_scope = GlobalLabelScope(set(['a', 'b']))
        file_scope = LabelScope(LabelScopeType.FILE, global_scope, 'mycode.py')
        local_scope = LabelScope(LabelScopeType.LOCAL, file_scope, 'my_label')

        local_scope.set_label_value('var1', 12, 1)

        self.assertEqual(local_scope.get_label_value('var1', 100), 12)
        with self.assertRaises(SystemExit, msg='register labels cannot have values'):
            local_scope.get_label_value('a', 101)
