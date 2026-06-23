import json


def upload_sample(client, headers, path, content_type):
    with open(path, "rb") as sample:
        return client.post(
            "/upload/file",
            headers=headers,
            data={"category": "Validation", "source": "Automated Test"},
            files={"file": (path.split("/")[-1], sample, content_type)},
        )


def test_upload_supported_formats_and_metadata(client, auth_headers):
    headers = auth_headers("instructor_alpha", "Inst123!")
    samples = [
        ("samples/training_performance.csv", "text/csv"),
        ("samples/training_performance.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("samples/war_report.pdf", "application/pdf"),
        ("samples/training_report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]

    uploaded = []
    for sample_path, content_type in samples:
        response = upload_sample(client, headers, sample_path, content_type)
        assert response.status_code == 200, response.text
        uploaded.append(response.json()["filename"])

    first_duplicate = upload_sample(client, headers, "samples/training_performance.csv", "text/csv")
    second_duplicate = upload_sample(client, headers, "samples/training_performance.csv", "text/csv")
    assert first_duplicate.status_code == 200
    assert second_duplicate.status_code == 200
    assert first_duplicate.json()["filename"] != second_duplicate.json()["filename"]

    documents = client.get("/documents/list", headers=headers)
    assert documents.status_code == 200
    assert len(documents.json()) >= 6
    parsed_metadata = [json.loads(doc["metadata"]) for doc in documents.json() if doc["metadata"]]
    assert all("original_filename" in item for item in parsed_metadata)
    assert all("saved_filename" in item for item in parsed_metadata)
    assert all(item["size_bytes"] > 0 for item in parsed_metadata)
