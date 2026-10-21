"""Synthetic login lifecycle and privilege-boundary checks. No LINE calls."""
import json
import os
import types
import unittest
from unittest.mock import Mock, patch
from test_scheduler import h, Table, ClientError
import cloud_login as login

class LoginTests(unittest.TestCase):
    def setUp(self):
        self.id="b"*32
        self.row={"id":"login","attempt":self.id,"status":"waiting","deadline":1100,"display_blob":"ciphertext"}
        h.jobs=Table();h.jobs.name="jobs";h.jobs.items["login"]=self.row
        h.session_table=Table();h.session_table.name="sessions"
        h.session_table.meta=types.SimpleNamespace(client=Mock())
        self.time=patch.object(login.time,"time",return_value=1000);self.time.start()
    def tearDown(self):self.time.stop()
    def data(self,result):return json.loads(result["body"])
    def test_wrong_attempt_cannot_read_display(self):
        with patch.object(login.subprocess,"run") as child,self.assertRaises(ValueError):
            login.api(h,{"action":"login_status","id":"a"*32})
        child.assert_not_called()
    def test_expired_attempt_never_decrypts(self):
        self.row["deadline"]=999
        with patch.object(login,"finish",side_effect=lambda *a:self.row.update(status="expired")),patch.object(login.subprocess,"run") as child:
            data=self.data(login.api(h,{"action":"login_status","id":self.id}))
        child.assert_not_called();self.assertEqual(data["login"]["status"],"expired");self.assertNotIn("ciphertext",json.dumps(data))
    def test_status_contains_only_display_not_ciphertext_or_session(self):
        child=types.SimpleNamespace(stdout=json.dumps({"ok":True,"data":{"kind":"pin","pin":"123456"}}))
        with patch.dict(os.environ,{"QR_KEY":"synthetic-display-key","SESSION_KEY":"synthetic-session-key","AWS_SECRET_ACCESS_KEY":"synthetic-role"}),patch.object(login.subprocess,"run",return_value=child) as run:
            data=self.data(login.api(h,{"action":"login_status","id":self.id}))
        invocation=run.call_args.kwargs
        self.assertNotIn("synthetic-session-key",invocation["input"])
        self.assertNotIn("AWS_SECRET_ACCESS_KEY",invocation["env"])
        self.assertEqual(data["login"]["pin"],"123456");self.assertNotIn("display_blob",json.dumps(data))
    def test_cancel_race_hides_already_decrypted_qr(self):
        def child(*a,**kw):
            self.row.update(status="cancelled")
            return types.SimpleNamespace(stdout=json.dumps({"ok":True,"data":{"qr":"synthetic-png"}}))
        with patch.dict(os.environ,{"QR_KEY":"synthetic"}),patch.object(login.subprocess,"run",side_effect=child):
            data=self.data(login.api(h,{"action":"login_status","id":self.id}))
        self.assertEqual(data["login"]["status"],"cancelled");self.assertNotIn("qr",data["login"])
    def test_start_same_id_does_not_dispatch_again(self):
        with patch.object(h,"invoke_worker") as invoke:
            result=login.api(h,{"action":"login_start","id":self.id})
        self.assertEqual(result["statusCode"],200);invoke.assert_not_called()
    def test_cooldown_rejection_does_not_dispatch(self):
        with patch.object(h.jobs,"put_item",side_effect=ClientError()),patch.object(h,"invoke_worker") as invoke:
            result=login.api(h,{"action":"login_start","id":"a"*32})
        self.assertEqual(result["statusCode"],409);invoke.assert_not_called()
    def test_completed_duplicate_worker_cannot_restart_login(self):
        self.row["status"]="connected"
        with patch.object(login.subprocess,"Popen") as process:
            self.assertEqual(login.run(h,"owner",self.id),{"ignored":True})
        process.assert_not_called()
    def test_commit_is_one_transaction_with_lock_attempt_expiry_and_version_fences(self):
        login.commit(h,"synthetic-ciphertext",7,"lease-owner",self.id)
        tx=h.session_table.meta.client.transact_write_items.call_args.kwargs["TransactItems"]
        self.assertEqual(len(tx),4)
        self.assertIn("#until > :now",tx[0]["ConditionCheck"]["ConditionExpression"])
        self.assertEqual(tx[1]["Put"]["ExpressionAttributeValues"][":v"],7)
        self.assertEqual(tx[1]["Put"]["Item"]["version"],8)
        self.assertIn("deadline > :now",tx[2]["Update"]["ConditionExpression"])
        self.assertIn("#s = :wait",tx[2]["Update"]["ConditionExpression"])
        self.assertEqual(tx[2]["Update"]["ExpressionAttributeValues"][":a"],self.id)
        self.assertIn("REMOVE display_blob",tx[2]["Update"]["UpdateExpression"])
        self.assertFalse(tx[3]["Put"]["Item"]["connected"])
    def test_initial_commit_requires_absent_session(self):
        login.commit(h,"synthetic",0,"owner",self.id)
        tx=h.session_table.meta.client.transact_write_items.call_args.kwargs["TransactItems"]
        self.assertEqual(tx[1]["Put"]["ConditionExpression"],"attribute_not_exists(id)")
    def test_cancel_cannot_overwrite_committed_login(self):
        with patch.object(h.jobs,"update_item",side_effect=ClientError()) as update:
            login.finish(h,self.id,"cancelled")
        self.assertIn("#s IN (:start,:wait)",update.call_args.kwargs["ConditionExpression"])
    def test_api_never_receives_session_key_or_session_permissions(self):
        from template import template
        resources=template()["Resources"]
        self.assertNotIn("Sessions",json.dumps(resources["APIRole"]))
        self.assertNotIn("SESSION_KEY",json.dumps(resources["API"]))
        self.assertIn("QR_KEY",resources["API"]["Properties"]["Environment"]["Variables"])

if __name__=="__main__":unittest.main()
