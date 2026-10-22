"""Photo groups: immutable inputs, sequential receipts, and no mutation replay."""
import json
import types
import unittest
from unittest.mock import Mock, patch

import test_scheduler as base
import handler as h


class PhotoWorkerTests(unittest.TestCase):
    setUp = base.SchedulerTests.setUp
    tearDown = base.SchedulerTests.tearDown
    run_worker = base.SchedulerTests.run_worker

    def photos(self, count=3):
        h.jobs.items[self.id]["photos"] = [{"name":f"photo-{i}.png"} for i in range(count)]

    def test_sequential_group_uses_receipt_id_and_persists_progress(self):
        self.photos(10)
        calls=[]
        def client(action,owner,chat,text,data):
            self.assertEqual(action,"send-image")
            self.assertEqual(h.jobs.items[self.id]["status"],"sending")
            i=len(calls)+1
            self.assertEqual(data["image_group"],{"id":"0" if i==1 else "12345","index":i,"total":10})
            if i>1:self.assertEqual(len(h.jobs.items[self.id]["result_info"]["receipts"]),i-1)
            calls.append(data)
            return {"status":"sent","message_id":str(i),"group_id":"12345","encrypted":True}
        with patch.object(h,"load_attachment",side_effect=lambda a:{"file_name":a["name"],"file_data":""}),patch.object(h,"delete_attachment"):
            self.run_worker(client)
            self.run_worker(lambda *a:self.fail("replayed group"))
        self.assertEqual(len(calls),10)
        self.assertEqual(h.jobs.items[self.id]["status"],"sent")

    def test_stops_after_first_uncertain_photo(self):
        for result in [{"status":"unknown"},{"status":"sent","encrypted":False},
                       {"status":"sent","encrypted":True,"group_id":"different"},OSError("private body")]:
            with self.subTest(result=result):
                h.jobs.items[self.id]["status"]="scheduled"
                self.photos()
                client=Mock(side_effect=[{"status":"sent","message_id":"1","group_id":"123","encrypted":True},result])
                with patch.object(h,"load_attachment",side_effect=lambda a:{}),patch.object(h,"delete_attachment"):
                    self.run_worker(client)
                    self.run_worker(lambda *a:self.fail("uncertain group replayed"))
                self.assertEqual(client.call_count,2)
                self.assertEqual(h.jobs.items[self.id]["status"],"unknown")
                self.assertEqual(len(h.jobs.items[self.id]["result_info"]["receipts"]),1)
                self.assertNotIn("private",json.dumps(h.jobs.items[self.id]))

    def test_integrity_failure_reports_partial_and_never_sends_remaining(self):
        self.photos()
        client=Mock(return_value={"status":"sent","message_id":"1","group_id":"123","encrypted":True})
        with patch.object(h,"load_attachment",side_effect=[{},ValueError("bad hash")]),patch.object(h,"delete_attachment"):
            self.run_worker(client)
        self.assertEqual(client.call_count,1)
        self.assertEqual(h.jobs.items[self.id]["status"],"partial")

    def test_single_photo_has_no_group_metadata(self):
        self.photos(1)
        def client(*args):
            self.assertNotIn("image_group",args[-1])
            return {"status":"sent","encrypted":True,"message_id":"1"}
        with patch.object(h,"load_attachment",return_value={}),patch.object(h,"delete_attachment"):
            self.run_worker(client)
        self.assertEqual(h.jobs.items[self.id]["status"],"sent")

    def test_accepted_photo_with_missing_group_retains_its_receipt(self):
        self.photos()
        client=Mock(return_value={"status":"unknown","accepted":True,"message_id":"known-id","encrypted":True})
        with patch.object(h,"load_attachment",return_value={}),patch.object(h,"delete_attachment"):
            self.run_worker(client)
        self.assertEqual(client.call_count,1)
        self.assertEqual(h.jobs.items[self.id]["status"],"unknown")
        self.assertEqual(h.jobs.items[self.id]["result_info"]["receipts"][0]["message_id"],"known-id")

    def test_deadline_stops_before_new_mutation(self):
        self.photos()
        self.context.get_remaining_time_in_millis=lambda:14000
        with patch.object(h,"delete_attachment"):
            self.run_worker(lambda *a:self.fail("started without time budget"))
        self.assertEqual(h.jobs.items[self.id]["status"],"failed")


class PhotoScheduleTests(unittest.TestCase):
    def setUp(self):
        h.jobs=base.Table()
        h.jobs.items["meta"]={"id":"meta","connected":True,"chats":[{"id":"c"+"0"*32,"name":"Synthetic"}]}
        self.ids=["b"*32,"c"*32]
        for photo_id in self.ids:h.jobs.items["upload_"+photo_id]={"id":"upload_"+photo_id}
        self.body={"action":"schedule","id":self.ids[0],"chat":"c"+"0"*32,"text":"","immediate":True,"photos":self.ids}

    def call(self, body):
        return h.controller({"headers":{"authorization":"Bearer synthetic"},"requestContext":{"http":{"method":"POST"}},"body":json.dumps(body)},None)

    def test_group_pins_all_versions_and_repeated_request_does_not_dispatch(self):
        with patch.object(h,"prepare_attachment",side_effect=lambda id,job:{"name":id+".png","key":"uploads/"+id,"version":"v1"}) as prepare,patch.object(h,"invoke_worker") as invoke:
            first=self.call(self.body);second=self.call(self.body)
        self.assertEqual(first["statusCode"],201)
        self.assertEqual(second["statusCode"],200)
        self.assertEqual(prepare.call_count,2)
        invoke.assert_called_once()
        self.assertEqual(h.jobs.items[self.ids[0]]["photo_ids"],self.ids)

    def test_group_membership_cannot_change_after_acceptance(self):
        with patch.object(h,"prepare_attachment",return_value={"name":"synthetic.png"}),patch.object(h,"invoke_worker"):
            self.call(self.body)
            self.assertEqual(self.call({**self.body,"photos":[self.ids[0]]})["statusCode"],409)

    def test_invalid_group_never_pins_or_dispatches(self):
        for photos in [[self.ids[0]]*2, ["bad"], [f"{i:032x}" for i in range(11)], "invalid"]:
            with patch.object(h,"prepare_attachment") as prepare,patch.object(h,"invoke_worker") as invoke:
                result=self.call({**self.body,"photos":photos})
                self.assertEqual(result["statusCode"],400)
                prepare.assert_not_called();invoke.assert_not_called()

    def test_cleanup_deletes_each_exact_pinned_version(self):
        photos=[{"key":"uploads/"+id,"version":"v1"} for id in self.ids]
        with patch.object(h,"objects") as objects,patch.dict(h.os.environ,{"FILES_BUCKET":"synthetic"}):
            h.delete_attachment({"photos":photos})
        self.assertEqual(objects.delete_object.call_count,2)
        self.assertEqual(objects.delete_object.call_args.kwargs["VersionId"],"v1")

if __name__=="__main__":unittest.main()
