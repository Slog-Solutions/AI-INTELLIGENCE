def test_login_refresh_profile_and_rbac(client, auth_headers):
    admin_headers = auth_headers()

    profile = client.get("/auth/me", headers=admin_headers)
    assert profile.status_code == 200
    assert profile.json()["username"] == "admin"
    assert profile.json()["role"] == "Super Admin"

    refresh = client.post("/auth/refresh", headers=admin_headers)
    assert refresh.status_code == 200
    assert refresh.json()["token_type"] == "bearer"
    assert refresh.json()["access_token"]

    users = client.get("/users/", headers=admin_headers)
    assert users.status_code == 200
    assert {user["username"] for user in users.json()} >= {
        "admin",
        "co_alpha",
        "instructor_alpha",
        "analyst_main",
    }

    analyst_headers = auth_headers("analyst_main", "Ana123!")
    forbidden_users = client.get("/users/", headers=analyst_headers)
    assert forbidden_users.status_code == 403

    with open("samples/training_performance.csv", "rb") as sample:
        forbidden_upload = client.post(
            "/upload/file",
            headers=analyst_headers,
            data={"category": "Training Reports", "source": "Validation"},
            files={"file": ("training_performance.csv", sample, "text/csv")},
        )
    assert forbidden_upload.status_code == 403
