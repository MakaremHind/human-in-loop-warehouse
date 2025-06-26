"""""Unit tests for tools.py

These tests cover every public @tool in tools.py. External dependencies such
as MQTT, snapshot_store and mqtt_listener.get are patched so the tests run in
isolation.

Run with:
    ~\human-in-loop-warehouse\warehouse_chat> pytest -q unit_test/test_tools.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import types
from unittest.mock import MagicMock
import pytest
import tools

class DummyEnv:
    def __init__(self, data):
        self.data = data

class DummySnapshotStore:
    def __init__(self, snapshots):
        self.snapshots = snapshots
    def get(self, topic):
        return self.snapshots.get(topic)

@pytest.fixture
def dummy_snapshot(monkeypatch):
    snapshots = {}
    monkeypatch.setattr(tools, "snapshot_store", DummySnapshotStore(snapshots))
    return snapshots

@pytest.fixture
def patch_get(monkeypatch):
    def _apply(data_map):
        def fake_get(topic):
            return data_map.get(topic)
        monkeypatch.setattr(tools, "get", fake_get)
    return _apply

def test_master_status_online(monkeypatch):
    monkeypatch.setattr(tools, "snapshot_store", DummySnapshotStore({
        "master/state": {"data": "online"}
    }))
    res = tools.master_status.invoke({})
    assert res == {"online": True, "info": "Master state: online"}

def test_master_status_offline(monkeypatch):
    monkeypatch.setattr(tools, "snapshot_store", DummySnapshotStore({
        "master/state": {"data": "OFFLINE"}
    }))
    res = tools.master_status.invoke({})
    assert res == {"online": False, "info": "Master state: offline"}

def _make_boxes_env():
    return DummyEnv({"boxes": [
        {"color": "red", "type": "small", "global_pose": {"x": 0}},
        {"color": "blue", "type": "large", "global_pose": {"x": 1}},
    ]})

def test_list_boxes(patch_get):
    patch_get({"mmh_cam/detected_boxes": _make_boxes_env()})
    boxes = tools.list_boxes.invoke({})
    assert boxes == [
        {"id": 0, "color": "red", "type": "small"},
        {"id": 1, "color": "blue", "type": "large"},
    ]

def test_find_box_found(patch_get):
    patch_get({"mmh_cam/detected_boxes": _make_boxes_env()})
    res = tools.find_box.invoke({"box_id": 1})
    assert res["found"] is True and res["color"] == "blue"

def test_find_box_not_found(patch_get):
    patch_get({"mmh_cam/detected_boxes": _make_boxes_env()})
    res = tools.find_box.invoke({"box_id": 5})
    assert res == {"found": False, "error": "box '5' not found"}

def test_find_box_by_color_found(patch_get):
    patch_get({"mmh_cam/detected_boxes": _make_boxes_env()})
    res = tools.find_box_by_color.invoke({"color": "Red"})
    assert res["found"] and res["color"] == "red"

def test_find_box_by_color_none(patch_get):
    patch_get({"mmh_cam/detected_boxes": _make_boxes_env()})
    res = tools.find_box_by_color.invoke({"color": "green"})
    assert res == {"found": False, "error": "box(color) 'green' not found"}

def _make_modules_env():
    return DummyEnv({"items": [
        {"namespace": "container_01", "pose": {"x": 0}},
        {"namespace": "dock_03", "pose": {"x": 1}},
    ]})

def test_list_modules(patch_get):
    patch_get({"base_01/base_module_visualization": _make_modules_env()})
    mods = tools.list_modules.invoke({})
    assert mods == ["container_01", "dock_03"]

def test_find_module_exact(patch_get):
    patch_get({"base_01/base_module_visualization": _make_modules_env()})
    res = tools.find_module.invoke({"namespace": "dock_03"})
    assert res["found"] and res["namespace"] == "dock_03"

def test_find_module_not_found(patch_get):
    patch_get({"base_01/base_module_visualization": _make_modules_env()})
    res = tools.find_module.invoke({"namespace": "unknown"})
    assert res == {"found": False, "error": "module 'unknown' not found"}

def test_list_orders(monkeypatch):
    monkeypatch.setattr(tools, "snapshot_store", DummySnapshotStore({
        "base_01/order_request/response/1": {"header": {"timestamp": 100}},
        "base_01/order_request/response/2": {"header": {"timestamp": 200}},
    }))
    res = tools.list_orders.invoke({})
    timestamps = [o["header"]["timestamp"] for o in res.get("orders", [])]
    assert res["found"] and timestamps == sorted(timestamps, reverse=True)

def test_list_orders_empty(monkeypatch):
    monkeypatch.setattr(tools, "snapshot_store", DummySnapshotStore({}))
    res = tools.list_orders.invoke({})
    assert res == {"found": False, "error": "No order responses present in snapshot_store."}

def test_find_last_order_success(monkeypatch):
    dummy = {"order": {"id": 7}}
    class DummyEnv(types.SimpleNamespace): pass
    def fake_normalize(msg): return DummyEnv(data=dummy)

    monkeypatch.setattr(tools, "normalize_message", fake_normalize)
    monkeypatch.setattr(tools, "snapshot_store", DummySnapshotStore({"base_01/order_request": dummy}))

    res = tools.find_last_order.invoke({})
    assert res == {"found": True, "order": {"id": 7}}

def test_find_last_order_none(monkeypatch):
    monkeypatch.setattr(tools, "snapshot_store", DummySnapshotStore({}))
    res = tools.find_last_order.invoke({})
    assert res == {"found": False, "error": "No recent order found."}

def test_confirm_last_order_success(monkeypatch):
    monkeypatch.setattr(tools, "_order_results", {"cid": {"success": True}})
    res = tools.confirm_last_order.invoke({})
    assert res["found"] and "completed successfully" in res["message"]

def test_confirm_last_order_empty(monkeypatch):
    monkeypatch.setattr(tools, "_order_results", {})
    res = tools.confirm_last_order.invoke({})
    assert res == {"found": False, "error": "No recent order result available."}

def test_diagnose_failure_transport(dummy_snapshot):
    dummy_snapshot["base_01/conveyor_01/transport/response"] = {"success": False}
    res = tools.diagnose_failure.invoke({})
    assert res["found"] and "Transport failure" in res["reason"]

def test_diagnose_failure_none(dummy_snapshot):
    dummy_snapshot.clear()
    res = tools.diagnose_failure.invoke({})
    assert res == {"found": False, "error": "No known failure messages found in relevant topics."}

def test_trigger_order_wrap_argument_error(monkeypatch):
    mock_tool = MagicMock()
    def fake_invoke(args):
        raise ValueError("Missing goal")
    mock_tool.invoke = fake_invoke
    monkeypatch.setattr(tools, "trigger_order", mock_tool)

    res = tools.trigger_order_wrap({"start": "container_01"})
    assert res["found"] is False

def test_trigger_order_wrap_success(monkeypatch, patch_get):
    patch_get({
        "base_01/base_module_visualization": _make_modules_env(),
        "mmh_cam/detected_boxes": _make_boxes_env(),
    })

    mock_tool = MagicMock()
    def fake_invoke(args):
        assert args["start_pose"] == {"x": 0}
        assert args["goal_pose"] == {"x": 1}
        assert args["box_color"] == "red"
        return {"found": True, "args": args}
    mock_tool.invoke = fake_invoke
    monkeypatch.setattr(tools, "trigger_order", mock_tool)

    res = tools.trigger_order_wrap({
        "start": "container_01",
        "goal": "dock_03",
        "box_id": 0,
    })
    assert res["found"] is True
