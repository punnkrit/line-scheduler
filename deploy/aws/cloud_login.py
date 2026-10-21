"""Short-lived QR attempts. Secrets only cross private pipes / encrypted records."""
import json
import os
import selectors
import subprocess
import time

ACTIVE = ("starting", "waiting")


def current(h, attempt):
    row = h.read(h.jobs, "login")
    if not row or row.get("attempt") != attempt:
        raise ValueError("Unknown login")
    return row


def live(row):
    return row.get("status") in ACTIVE and int(row["deadline"]) > time.time()


def finish(h, attempt, status):
    try:
        h.jobs.update_item(Key={"id":"login"},
            UpdateExpression="SET #s = :end REMOVE display_blob",
            ConditionExpression="attempt = :a AND #s IN (:start,:wait)",
            ExpressionAttributeNames={"#s":"status"},
            ExpressionAttributeValues={":a":attempt,":start":"starting",":wait":"waiting",":end":status})
    except h.ClientError as exc:
        if not h.conditional(exc): raise


def api(h, body):
    attempt = body.get("id", "")
    if not isinstance(attempt,str) or not h.ID.fullmatch(attempt):
        return h.response(400,{"error":"Invalid login attempt"})
    action = body["action"]
    if action == "login_start":
        old = h.read(h.jobs,"login")
        if old and old.get("attempt") == attempt:
            return h.response(200,{"login":{"id":attempt,"status":old["status"],"deadline":old["deadline"]}})
        now = int(time.time())
        # A single row reserves the account, with a durable per-account cooldown.
        try:
            h.jobs.put_item(Item={"id":"login","attempt":attempt,"status":"starting",
                "deadline":now+150,"next_at":now+60,"expires_at":now+86400},
                ConditionExpression="attribute_not_exists(id) OR (next_at <= :now AND (#s IN (:done,:fail,:cancel,:expired) OR deadline <= :now))",
                ExpressionAttributeNames={"#s":"status"},
                ExpressionAttributeValues={":now":now,":done":"connected",":fail":"failed",":cancel":"cancelled",":expired":"expired"})
        except h.ClientError as exc:
            if h.conditional(exc):return h.response(409,{"error":"Another login is active or just ended. Wait a minute before starting again."})
            raise
        # Lost dispatch responses never trigger a second login. Expiry allows a fresh attempt.
        h.invoke_worker({"action":"login","attempt":attempt})
        return h.response(202,{"login":{"id":attempt,"status":"starting","deadline":now+150}})
    row = current(h,attempt)
    if row["status"] in ACTIVE and not live(row):
        finish(h,attempt,"expired");row=current(h,attempt)
    if action == "login_cancel":
        finish(h,attempt,"cancelled");row=current(h,attempt)
    elif action != "login_status":
        return h.response(400,{"error":"Invalid login action"})
    data={"id":attempt,"status":row["status"],"deadline":row["deadline"]}
    if action=="login_status" and live(row) and row.get("display_blob"):
        # API receives QR_KEY only; SESSION_KEY and the sessions table stay inaccessible.
        payload={"action":"login-view","qr_key":os.environ["QR_KEY"],"attempt":attempt,"blob":row["display_blob"]}
        result=subprocess.run(["/var/task/cloudline"],input=json.dumps(payload)+"\n",capture_output=True,
            text=True,timeout=5,env={"PATH":"/usr/bin:/bin","HOME":"/tmp","LANG":"C.UTF-8"})
        decoded=json.loads(result.stdout)
        if not decoded.get("ok"):raise ValueError("QR display unavailable")
        # Recheck after decryption so cancellation/success does not return stale QR/PIN.
        latest=current(h,attempt)
        if live(latest) and latest.get("display_blob")==row["display_blob"]:
            data.update(decoded["data"])
        else:data={"id":attempt,"status":latest["status"],"deadline":latest["deadline"]}
    return h.response(200,{"login":data})


def commit(h, blob, version, owner, attempt):
    now=int(time.time())
    condition={"ConditionExpression":"attribute_not_exists(id)"} if version==0 else {
        "ConditionExpression":"#v = :v","ExpressionAttributeNames":{"#v":"version"},"ExpressionAttributeValues":{":v":version}}
    h.session_table.meta.client.transact_write_items(TransactItems=[
        {"ConditionCheck":{"TableName":h.session_table.name,"Key":{"id":"lock"},
            "ConditionExpression":"#owner = :owner AND #until > :now",
            "ExpressionAttributeNames":{"#owner":"owner","#until":"until"},
            "ExpressionAttributeValues":{":owner":owner,":now":now}}},
        {"Put":{"TableName":h.session_table.name,"Item":{"id":"session","blob":blob,"version":version+1},**condition}},
        {"Update":{"TableName":h.jobs.name,"Key":{"id":"login"},
            "UpdateExpression":"SET #s = :done REMOVE display_blob",
            "ConditionExpression":"attempt = :a AND #s = :wait AND deadline > :now",
            "ExpressionAttributeNames":{"#s":"status"},
            "ExpressionAttributeValues":{":a":attempt,":wait":"waiting",":done":"connected",":now":now}}},
        {"Put":{"TableName":h.jobs.name,"Item":{"id":"meta","connected":False,"chats":[],"error":"Refresh conversations to finish connecting."}}}
    ])


def run(h, owner, attempt):
    row=current(h,attempt)
    if not live(row) or row["status"]!="starting":return {"ignored":True}
    # The worker already holds the account lease. Duplicate invocations cannot restart login.
    deadline=min(int(row["deadline"]),int(time.time())+105)
    try:
        h.jobs.update_item(Key={"id":"login"},UpdateExpression="SET #s = :wait, deadline = :deadline",
            ConditionExpression="attempt = :a AND #s = :start AND deadline > :now",
            ExpressionAttributeNames={"#s":"status"},
            ExpressionAttributeValues={":a":attempt,":start":"starting",":wait":"waiting",":now":int(time.time()),":deadline":deadline})
    except h.ClientError as exc:
        if h.conditional(exc):return {"ignored":True}
        raise
    saved=h.read(h.session_table,"session") or {"version":0,"blob":""}
    process=None
    try:
        h.jobs.update_item(Key={"id":"meta"},UpdateExpression="SET connected = :c, #e = :e",
            ExpressionAttributeNames={"#e":"error"},ExpressionAttributeValues={":c":False,":e":"LINE login in progress."})
        process=subprocess.Popen(["/var/task/cloudline"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env={"PATH":"/usr/bin:/bin","HOME":"/tmp","LANG":"C.UTF-8"})
        payload={"action":"login","key":os.environ["SESSION_KEY"],"qr_key":os.environ["QR_KEY"],
            "blob":saved["blob"],"attempt":attempt}
        process.stdin.write((json.dumps(payload)+"\n").encode());process.stdin.flush()
        buffer=b""
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while time.time()<deadline:
                row=current(h,attempt)
                if not live(row):break
                if not selector.select(timeout=2):continue
                chunk=os.read(process.stdout.fileno(),65536)
                if not chunk:break
                buffer+=chunk
                if len(buffer)>2*1024*1024:raise ValueError("Oversized response")
                while b"\n" in buffer:
                    line,buffer=buffer.split(b"\n",1);message=json.loads(line)
                    if message.get("op")=="login_event":
                        h.jobs.update_item(Key={"id":"login"},UpdateExpression="SET display_blob = :blob",
                            ConditionExpression="attempt = :a AND #s = :wait AND deadline > :now",
                            ExpressionAttributeNames={"#s":"status"},
                            ExpressionAttributeValues={":a":attempt,":wait":"waiting",":now":int(time.time()),":blob":message["blob"]})
                        process.stdin.write(b'{"ok":true}\n');process.stdin.flush()
                    elif message.get("op")=="save":
                        commit(h,message["blob"],int(saved["version"]),owner,attempt)
                        # The atomic commit is authoritative even if the acknowledgement pipe breaks.
                        try:process.stdin.write(b'{"ok":true}\n');process.stdin.flush();process.wait(timeout=3)
                        except (OSError,subprocess.TimeoutExpired):pass
                        return {"connected":True}
                    elif message.get("op")=="result":
                        raise ValueError("Login did not commit")
                    else:raise ValueError("Invalid login event")
        finish(h,attempt,"expired" if time.time()>=deadline else "failed")
    except Exception:
        # Never expose protocol errors, QR content, PINs, or session blobs.
        finish(h,attempt,"failed")
    finally:
        if process is not None:
            if process.poll() is None:process.kill()
            process.wait();process.stdin.close();process.stdout.close()
    return {"completed":False}
