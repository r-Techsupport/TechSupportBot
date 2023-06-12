from extensions import htd
from unittest.mock import patch

def setup_local_extension():
    with patch("asyncio.create_task", return_value=None):
        return htd.Htd(None)

class Test_SplitNicely:
    """A set of tests to test split_nicely"""
    def test_single_number(self):
        """A test to ensure that when just a single number is passed, 
        only a single entry is returned"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("5")

        # Step 3 - Assert that everything works
        assert output == ['5']

    def test_simple_equation(self):
        """A test to ensure that equations are split properly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("5+5")

        # Step 3 - Assert that everything works
        assert output == ['5', '+', '5']
    
    def test_negative(self):
        """A test to ensure that negatives are handled properly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("-2")

        # Step 3 - Assert that everything works
        assert output == ['-2']
    
    def test_double_minus(self):
        """A test to ensure that 2 minus signs in a row are handled properly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("5--8")

        # Step 3 - Assert that everything works
        assert output == ['5', '-', '-8']
    
    def test_every_operator(self):
        """A test to ensure that every operator is recognized"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("1+2-3*4/5")

        # Step 3 - Assert that everything works
        assert output == ['1', '+', '2', '-', '3', '*', '4', '/', '5']
    
    def test_long_number(self):
        """A test to ensure that long numbers are added correctly"""
        # Step 1 - Setup env
        hextodec = setup_local_extension()

        # Step 2 - Call the function
        output = hextodec.split_nicely("3276856238658273658724658247658245")

        # Step 3 - Assert that everything works
        assert output == ['3276856238658273658724658247658245']