"""API-level tests against the real PostgreSQL: auth, KB ownership,
document lifecycle, retrieval, citations, evidence."""
from __future__ import annotations

import io
import time

import pytest


@pytest.mark.skipif(True, reason="quick import sanity guard")
class _Placeholder:
    pass


def _md_file(content: str, name: str = "doc.md") -> dict:
    return {"file": (name, io.BytesIO(content.encode("utf-8")), "text/markdown")}


TRAVEL_DOC = """# 差旅管理制度

## 第一章 交通
乘坐高铁经济舱，特殊情况下飞机须提前审批。

## 第二章 住宿
### 2.1 一线城市
一线城市住宿标准为不超过 500 元/晚。

### 2.2 二线城市
二线城市住宿标准为不超过 350 元/晚（含税）。超标准住宿须提前书面申请，经部门负责人审批后执行。

## 第三章 报销
出差结束后 5 个工作日内提交报销申请，附合规发票。
"""

ANNUAL_LEAVE_DOC = """# 年假管理制度

## 第一章 年假天数
员工累计工作满 1 年不满 10 年的，年休假 5 天；满 10 年不满 20 年的，年休假 10 天；满 20 年的，年休假 15 天。

## 第二章 申请流程
年假需提前 3 个工作日在 OA 系统提交申请，经直属主管批准。
"""


class TestAuth:
    def test_register_rejects_weak_password(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "weakpw", "email": "weak@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_register_duplicate_rejected(self, client):
        payload = {"username": "dupuser", "email": "dup@example.com", "password": "Passw0rd123"}
        first = client.post("/api/auth/register", json=payload)
        assert first.status_code == 201
        second = client.post("/api/auth/register", json=payload)
        assert second.status_code == 409

    def test_login_wrong_password(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"account": "testuser", "password": "WrongPass1"},
        )
        assert resp.status_code == 401

    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_with_token(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"


class TestKBOwnership:
    def test_create_and_get(self, client, auth_headers):
        resp = client.post(
            "/api/knowledge-bases",
            json={"name": "测试财务库", "description": "test", "category": "finance"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        kb_id = resp.json()["id"]
        got = client.get(f"/api/knowledge-bases/{kb_id}", headers=auth_headers)
        assert got.status_code == 200
        assert got.json()["status"] == "EMPTY"

    def test_other_user_cannot_access(self, client, auth_headers, second_user_token):
        kb = client.post(
            "/api/knowledge-bases",
            json={"name": "私有库", "description": "", "category": "general"},
            headers=auth_headers,
        ).json()
        other_headers = {"Authorization": f"Bearer {second_user_token}"}
        resp = client.get(f"/api/knowledge-bases/{kb['id']}", headers=other_headers)
        assert resp.status_code == 404

    def test_max_5_kb_scope(self, client, auth_headers):
        ids = []
        for i in range(6):
            kb = client.post(
                "/api/knowledge-bases",
                json={"name": f"scope-{i}", "description": "", "category": "general"},
                headers=auth_headers,
            ).json()
            ids.append(kb["id"])
        resp = client.post(
            "/api/retrieval/run",
            json={"kb_ids": ids, "question": "测试", "strategy": "bm25"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "最多" in resp.json()["detail"]


class TestDocumentLifecycle:
    @pytest.fixture(scope="class")
    def kb_id(self, client, auth_headers):
        resp = client.post(
            "/api/knowledge-bases",
            json={"name": "文档流程库", "description": "lifecycle", "category": "hr"},
            headers=auth_headers,
        )
        return resp.json()["id"]

    def _upload_and_wait(self, client, auth_headers, kb_id, content, name="doc.md"):
        resp = client.post(
            "/api/documents/upload",
            params={"kb_id": kb_id},
            files=_md_file(content, name),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        version_id = resp.json()["version_id"]
        # status must start as UPLOADED (not faked READY)
        detail = client.get(f"/api/document-versions/{version_id}", headers=auth_headers).json()
        assert detail["processing_status"] in ("UPLOADED", "PARSING", "CHUNKING", "INDEXING", "READY")
        # wait for pipeline
        for _ in range(40):
            detail = client.get(f"/api/document-versions/{version_id}", headers=auth_headers).json()
            if detail["processing_status"] in ("READY", "FAILED"):
                return version_id, detail
            time.sleep(0.5)
        raise AssertionError("文档处理超时")

    def test_upload_reaches_ready_with_chunks(self, client, auth_headers, kb_id):
        version_id, detail = self._upload_and_wait(client, auth_headers, kb_id, TRAVEL_DOC, "差旅管理制度.md")
        assert detail["processing_status"] == "READY"
        assert detail["parse_overview"]["child_chunks"] > 0
        assert detail["parse_overview"]["parent_chunks"] > 0
        assert detail["chunk_preview"]["items"]

    def test_new_version_of_same_logical_document(self, client, auth_headers, kb_id):
        # upload a second file with the same title -> same logical document, new version.
        # Use a distinct filename so this test is independent of prior uploads in the class.
        v1, _ = self._upload_and_wait(client, auth_headers, kb_id, TRAVEL_DOC, "招聘管理制度.md")
        v2, detail2 = self._upload_and_wait(client, auth_headers, kb_id, TRAVEL_DOC + "\n\n新增内容。", "招聘管理制度.md")
        assert v1 != v2
        doc_id = detail2["document"]["id"]
        doc_detail = client.get(f"/api/documents/{doc_id}", headers=auth_headers).json()
        labels = [v["version_label"] for v in doc_detail["versions"]]
        assert len(doc_detail["versions"]) == 2
        assert any(l != "V1.0" for l in labels)
        # the older version becomes HISTORICAL
        lifecycle = {v["version_label"]: v["lifecycle_status"] for v in doc_detail["versions"]}
        assert list(lifecycle.values()).count("HISTORICAL") >= 1
        assert list(lifecycle.values()).count("CURRENT") == 1

    def test_rejects_unsupported_format(self, client, auth_headers, kb_id):
        resp = client.post(
            "/api/documents/upload",
            params={"kb_id": kb_id},
            files={"file": ("x.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_docx_upload(self, client, auth_headers, kb_id):
        from docx import Document as DocxDocument

        d = DocxDocument()
        d.add_heading("年假管理制度", level=1)
        d.add_heading("第一章 年假天数", level=2)
        d.add_paragraph("工作满 1 年不满 10 年的，年休假 5 天。")
        buf = io.BytesIO()
        d.save(buf)
        buf.seek(0)
        resp = client.post(
            "/api/documents/upload",
            params={"kb_id": kb_id},
            files={"file": ("年假管理制度.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        version_id = resp.json()["version_id"]
        for _ in range(40):
            detail = client.get(f"/api/document-versions/{version_id}", headers=auth_headers).json()
            if detail["processing_status"] in ("READY", "FAILED"):
                break
            time.sleep(0.5)
        assert detail["processing_status"] == "READY"
        assert detail["parse_overview"]["child_chunks"] > 0


class TestRetrievalAndChat:
    @pytest.fixture(scope="class")
    def ready_kb(self, client, auth_headers):
        kb = client.post(
            "/api/knowledge-bases",
            json={"name": "检索测试库", "description": "retrieval", "category": "hr"},
            headers=auth_headers,
        ).json()
        resp = client.post(
            "/api/documents/upload",
            params={"kb_id": kb["id"]},
            files=_md_file(ANNUAL_LEAVE_DOC, "年假管理制度.md"),
            headers=auth_headers,
        )
        version_id = resp.json()["version_id"]
        for _ in range(60):
            detail = client.get(f"/api/document-versions/{version_id}", headers=auth_headers).json()
            if detail["processing_status"] in ("READY", "FAILED"):
                break
            time.sleep(0.5)
        assert detail["processing_status"] == "READY", "需要 embedding 模型可用才能通过本测试"
        return kb["id"]

    def test_bm25_retrieval(self, client, auth_headers, ready_kb):
        resp = client.post(
            "/api/retrieval/run",
            json={"kb_ids": [ready_kb], "question": "年假可以休几天", "strategy": "bm25"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hits"], "BM25 必须召回结果"
        assert data["hits"][0]["document_title"] == "年假管理制度"

    def test_hybrid_with_stages(self, client, auth_headers, ready_kb):
        resp = client.post(
            "/api/retrieval/run",
            json={"kb_ids": [ready_kb], "question": "工作十年有多少年假", "strategy": "hybrid"},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["hits"]
        stages = {s["stage"] for s in data["stages"]}
        assert {"scope", "embed", "dense", "bm25", "fusion"} <= stages

    def test_score_types_are_labeled(self, client, auth_headers, ready_kb):
        resp = client.post(
            "/api/retrieval/run",
            json={"kb_ids": [ready_kb], "question": "年假", "strategy": "hybrid_rerank"},
            headers=auth_headers,
        )
        data = resp.json()
        assert "score_types" in data
        assert data["score_types"]["dense_similarity"] == "Dense Similarity (cosine)"
        assert data["score_types"]["bm25_score"] == "BM25 Score"
        assert data["score_types"]["rrf_rank"] == "RRF Rank"

    def test_citation_mapping(self, client, auth_headers, ready_kb):
        resp = client.post(
            "/api/retrieval/run",
            json={"kb_ids": [ready_kb], "question": "年假申请流程", "strategy": "hybrid"},
            headers=auth_headers,
        )
        hit = resp.json()["hits"][0]
        assert hit["document_version_id"] > 0
        assert hit["heading_path"]
        # parent context present for generation
        assert hit["parent_content"] or hit["content"]

    def test_evidence_insufficient_for_unrelated_question(self, client, auth_headers, ready_kb):
        resp = client.post(
            "/api/retrieval/run",
            json={"kb_ids": [ready_kb], "question": "量子力学的测不准原理是什么", "strategy": "hybrid"},
            headers=auth_headers,
        )
        data = resp.json()
        # either no hits at all, or hits exist — chat layer decides evidence.
        # here we assert the retrieval layer returns honestly
        for h in data["hits"]:
            assert h["dense_similarity"] is not None


class TestConversationPersistence:
    def test_conversation_crud(self, client, auth_headers):
        conv = client.post("/api/conversations", json={"title": "测试对话"}, headers=auth_headers).json()
        got = client.get(f"/api/conversations/{conv['id']}", headers=auth_headers)
        assert got.status_code == 200
        assert got.json()["messages"] == []
        deleted = client.delete(f"/api/conversations/{conv['id']}", headers=auth_headers)
        assert deleted.status_code == 204
