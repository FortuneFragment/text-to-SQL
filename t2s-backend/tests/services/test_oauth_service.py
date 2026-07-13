from __future__ import annotations

import pytest

from services.auth.oauth_service import normalize_profile


def _wrapped_profile() -> dict:
    return {
        "code": "ok",
        "state": True,
        "message": "",
        "data": {
            "user": {
                "identity": "role-id",
                "uniCode": "user-id",
                "name": "用户A",
                "people": {
                    "name": "用户A",
                    "uniCode": "user-id",
                    "email": "",
                    "roles": [
                        {
                            "identity": "role-id",
                            "orgnization": {
                                "uniCode": "org-id",
                                "code": "22800",
                                "name": "信息科学与工程学院",
                                "fullName": "教学机构/信息科学与工程学院",
                            },
                            "type": {
                                "uniCode": "type-id",
                                "code": "Z-3",
                                "name": "研究生",
                            },
                        }
                    ],
                },
            }
        },
    }


def test_normalize_profile_accepts_school_wrapped_response():
    profile = normalize_profile(
        _wrapped_profile(),
        expected_uni_code="user-id",
    )

    assert profile.uni_code == "user-id"
    assert profile.name == "用户A"
    assert profile.email == ""
    assert profile.roles == [
        {
            "identity": "role-id",
            "organization": {
                "uniCode": "org-id",
                "code": "22800",
                "name": "信息科学与工程学院",
                "fullName": "教学机构/信息科学与工程学院",
            },
            "type": {
                "uniCode": "type-id",
                "code": "Z-3",
                "name": "研究生",
            },
        }
    ]


def test_normalize_profile_accepts_documented_raw_response():
    profile = normalize_profile(
        {
            "uniCode": "user-id",
            "name": "用户A",
            "email": "user@example.edu.cn",
            "state": 0,
            "roles": [],
        },
        expected_uni_code="user-id",
    )

    assert profile.uni_code == "user-id"
    assert profile.name == "用户A"
    assert profile.email == "user@example.edu.cn"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "code": "error",
            "state": False,
            "message": "token invalid",
            "data": None,
        },
        {
            "code": "error",
            "state": True,
            "message": "user unavailable",
            "data": None,
        },
        {
            "code": "error",
            "state": False,
            "message": "user unavailable",
            "uniCode": "user-id",
        },
    ],
)
def test_normalize_profile_rejects_failed_wrapped_response(payload):
    with pytest.raises(ValueError, match="OAuth 用户信息获取失败"):
        normalize_profile(payload, expected_uni_code="user-id")


def test_normalize_profile_requires_user_info_uni_code():
    with pytest.raises(ValueError, match="OAuth 用户信息缺少 uniCode"):
        normalize_profile(
            {
                "code": "ok",
                "state": True,
                "data": {
                    "user": {
                        "identity": "role-id",
                        "name": "用户A",
                        "people": {},
                    }
                },
            },
            expected_uni_code="user-id",
        )
