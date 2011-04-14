import unittest
import test_fuzzy_path_handler as fuzzy
import test_ges_rpc_methods as gesrpc

if __name__ == "__main__":
    testresults = []
    tests = [fuzzy, gesrpc]
    for t in tests:
        print('\nTESTING:\n%s\n' % t)
        testresults.append( 
            unittest.TextTestRunner(verbosity=2).run( t.suite() )
        )
    # print("\nRESULTS:\n")
    # for t, tr in zip(tests, testresults):
    
        # print dir(tr)
        # if tr.wasSuccessful:
            # print "SUCCESS - %s\n" % t
        # else:
            # print "FAIL - %s\n" % t