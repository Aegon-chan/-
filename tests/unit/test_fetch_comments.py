"""Tests for the GitHub PR comments fetching logic (fetch_comments.py).

Tests cover all functions in the script via mocking of subprocess calls
to avoid requiring a real GitHub CLI installation.
"""
from __future__ import annotations

import importlib.util
import pathlib
from unittest.mock import MagicMock, patch

import pytest


# -- module loading -----------------------------------------------------------

_PLUGIN_SCRIPT = pathlib.Path(
    "C:/Users/24622/.codex/plugins/cache/openai-api-curated/"
    "github/11c74d6b/skills/gh-address-comments/scripts/fetch_comments.py"
)


@pytest.fixture(scope="module")
def mod():
    """Load fetch_comments.py once per test module."""
    spec = importlib.util.spec_from_file_location("fetch_comments", str(_PLUGIN_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- helpers ------------------------------------------------------------------


def _mock_subprocess(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a fake subprocess.CompletedProcess."""
    p = MagicMock()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


def _pr_page(
    *,
    comments_nodes: list | None = None,
    reviews_nodes: list | None = None,
    threads_nodes: list | None = None,
    has_next_c: bool = False,
    has_next_r: bool = False,
    has_next_t: bool = False,
    pr_number: int = 1,
    pr_url: str = "https://github.com/o/r/pull/1",
    pr_title: str = "Test PR",
    pr_state: str = "OPEN",
    override_pr: dict | None = None,
) -> dict:
    """Build a single-page GraphQL response fragment for tests."""
    pr = {
        "number": pr_number,
        "url": pr_url,
        "title": pr_title,
        "state": pr_state,
        "comments": {
            "pageInfo": {"hasNextPage": has_next_c, "endCursor": "c2" if has_next_c else None},
            "nodes": comments_nodes or [],
        },
        "reviews": {
            "pageInfo": {"hasNextPage": has_next_r, "endCursor": "r2" if has_next_r else None},
            "nodes": reviews_nodes or [],
        },
        "reviewThreads": {
            "pageInfo": {"hasNextPage": has_next_t, "endCursor": "t2" if has_next_t else None},
            "nodes": threads_nodes or [],
        },
    }
    if override_pr:
        pr.update(override_pr)
    return {"data": {"repository": {"pullRequest": pr}}}


# -- _run --------------------------------------------------------------------


class TestRun:
    """Tests for fetch_comments._run()."""

    def test_returns_stdout_on_success(self, mod):
        with patch.object(mod.subprocess, "run", return_value=_mock_subprocess(stdout="hello")):
            assert mod._run(["echo", "hello"]) == "hello"

    def test_passes_stdin(self, mod):
        with patch.object(mod.subprocess, "run", return_value=_mock_subprocess(stdout="ok")):
            mod._run(["cat"], stdin="data")
            mod.subprocess.run.assert_called_once_with(
                ["cat"], input="data", capture_output=True, text=True
            )

    def test_default_stdin_is_none(self, mod):
        with patch.object(mod.subprocess, "run", return_value=_mock_subprocess(stdout="")):
            mod._run(["echo", "hi"])
            mod.subprocess.run.assert_called_once_with(
                ["echo", "hi"], input=None, capture_output=True, text=True
            )

    def test_raises_on_nonzero_exit(self, mod):
        with patch.object(
            mod.subprocess, "run", return_value=_mock_subprocess(returncode=1, stderr="oops"),
        ):
            with pytest.raises(RuntimeError, match="Command failed"):
                mod._run(["false"])

    def test_error_includes_cmd_and_stderr(self, mod):
        with patch.object(
            mod.subprocess, "run", return_value=_mock_subprocess(returncode=127, stderr="not found"),
        ):
            with pytest.raises(RuntimeError) as exc:
                mod._run(["nonexistent", "--flag"])
            assert "nonexistent" in str(exc.value)
            assert "not found" in str(exc.value)


# -- _run_json ----------------------------------------------------------------


class TestRunJson:
    """Tests for fetch_comments._run_json()."""

    def test_parses_valid_json(self, mod):
        data = {"key": "value", "nested": [1, 2, 3]}
        with patch.object(mod, "_run", return_value='{"key": "value", "nested": [1, 2, 3]}'):
            assert mod._run_json([]) == data

    def test_returns_empty_dict_on_empty_object(self, mod):
        with patch.object(mod, "_run", return_value="{}"):
            assert mod._run_json([]) == {}

    def test_raises_on_invalid_json(self, mod):
        with patch.object(mod, "_run", return_value="not-json"):
            with pytest.raises(RuntimeError, match="Failed to parse JSON"):
                mod._run_json([])

    def test_passes_stdin_through(self, mod):
        with patch.object(mod, "_run", return_value="{}"):
            mod._run_json(["cmd"], stdin="data")
            mod._run.assert_called_once_with(["cmd"], stdin="data")

    def test_no_stdin_by_default(self, mod):
        with patch.object(mod, "_run", return_value="{}"):
            mod._run_json(["cmd"])
            mod._run.assert_called_once_with(["cmd"], stdin=None)


# -- _ensure_gh_authenticated ------------------------------------------------


class TestEnsureGhAuthenticated:
    """Tests for fetch_comments._ensure_gh_authenticated()."""

    def test_success_does_not_raise(self, mod):
        with patch.object(mod, "_run", return_value="logged in to github.com"):
            mod._ensure_gh_authenticated()

    def test_failure_raises_with_login_help(self, mod):
        with patch.object(mod, "_run", side_effect=RuntimeError("auth failed")):
            with pytest.raises(RuntimeError, match="gh auth login"):
                mod._ensure_gh_authenticated()

    def test_failure_prints_guidance_to_stderr(self, mod):
        with (
            patch.object(mod, "_run", side_effect=RuntimeError("auth failed")),
            patch.object(mod.sys, "stderr") as mock_stderr,
        ):
            with pytest.raises(RuntimeError):
                mod._ensure_gh_authenticated()
            mock_stderr.write.assert_any_call(
                "run `gh auth login` to authenticate the GitHub CLI"
            )

# -- gh_pr_view_json ----------------------------------------------------------


class TestGhPrViewJson:
    """Tests for fetch_comments.gh_pr_view_json()."""

    def test_calls_run_json_with_correct_args(self, mod):
        expected = {"number": 42}
        with patch.object(mod, "_run_json", return_value=expected):
            result = mod.gh_pr_view_json("number,headRepositoryOwner,headRepository")
            mod._run_json.assert_called_once_with(
                ["gh", "pr", "view", "--json", "number,headRepositoryOwner,headRepository"]
            )
            assert result == expected


# -- get_current_pr_ref -------------------------------------------------------


class TestGetCurrentPrRef:
    """Tests for fetch_comments.get_current_pr_ref()."""

    def test_returns_owner_repo_number(self, mod):
        response = {
            "number": 7,
            "headRepositoryOwner": {"login": "my-org"},
            "headRepository": {"name": "my-repo"},
        }
        with patch.object(mod, "gh_pr_view_json", return_value=response):
            owner, repo, number = mod.get_current_pr_ref()
            assert (owner, repo, number) == ("my-org", "my-repo", 7)

    def test_handles_cross_repo_fork(self, mod):
        """Fork PRs use headRepositoryOwner which differs from base repo."""
        response = {
            "number": 42,
            "headRepositoryOwner": {"login": "fork-owner"},
            "headRepository": {"name": "forked-repo"},
        }
        with patch.object(mod, "gh_pr_view_json", return_value=response):
            owner, repo, number = mod.get_current_pr_ref()
            assert owner == "fork-owner"
            assert repo == "forked-repo"

    def test_passes_correct_fields(self, mod):
        with patch.object(mod, "gh_pr_view_json", return_value={
            "number": 1,
            "headRepositoryOwner": {"login": "o"},
            "headRepository": {"name": "r"},
        }):
            mod.get_current_pr_ref()
            mod.gh_pr_view_json.assert_called_once_with(
                "number,headRepositoryOwner,headRepository"
            )

# -- gh_api_graphql -----------------------------------------------------------


class TestGhApiGraphql:
    """Tests for fetch_comments.gh_api_graphql()."""

    BASE = ["gh", "api", "graphql", "-F", "query=@-"]

    def test_minimal_command_no_cursors(self, mod):
        with patch.object(mod, "_run_json", return_value={}) as mock_run_json:
            mod.gh_api_graphql("owner", "repo", 1)
        expected = self.BASE + [
            "-F", "owner=owner",
            "-F", "repo=repo",
            "-F", "number=1",
        ]
        mock_run_json.assert_called_once_with(expected, stdin=mod.QUERY)

    def test_with_all_cursors(self, mod):
        with patch.object(mod, "_run_json", return_value={}) as mock_run_json:
            mod.gh_api_graphql("o", "r", 1, comments_cursor="c1", reviews_cursor="r1", threads_cursor="t1")
        expected = (
            self.BASE
            + ["-F", "owner=o", "-F", "repo=r", "-F", "number=1"]
            + ["-F", "commentsCursor=c1", "-F", "reviewsCursor=r1", "-F", "threadsCursor=t1"]
        )
        mock_run_json.assert_called_once_with(expected, stdin=mod.QUERY)

    def test_omits_null_cursors(self, mod):
        with patch.object(mod, "_run_json", return_value={}) as mock_run_json:
            mod.gh_api_graphql("o", "r", 1, comments_cursor=None, reviews_cursor="r1", threads_cursor=None)
        expected = (
            self.BASE
            + ["-F", "owner=o", "-F", "repo=r", "-F", "number=1"]
            + ["-F", "reviewsCursor=r1"]
        )
        mock_run_json.assert_called_once_with(expected, stdin=mod.QUERY)

    def test_only_comments_cursor(self, mod):
        with patch.object(mod, "_run_json", return_value={}) as mock_run_json:
            mod.gh_api_graphql("o", "r", 1, comments_cursor="c1", reviews_cursor=None, threads_cursor=None)
        expected = (
            self.BASE
            + ["-F", "owner=o", "-F", "repo=r", "-F", "number=1"]
            + ["-F", "commentsCursor=c1"]
        )
        mock_run_json.assert_called_once_with(expected, stdin=mod.QUERY)


# -- fetch_all ----------------------------------------------------------------


class TestFetchAll:
    """Tests for fetch_comments.fetch_all()."""

    def test_single_page_all_collections(self, mod):
        page = _pr_page(
            comments_nodes=[{"id": "c1", "body": "Nice PR"}],
            reviews_nodes=[{"id": "r1", "state": "APPROVED"}],
            threads_nodes=[{"id": "t1", "path": "src/main.py", "isResolved": True}],
        )
        with patch.object(mod, "gh_api_graphql", return_value=page):
            result = mod.fetch_all("o", "r", 1)

        assert result["pull_request"] == {
            "number": 1,
            "url": "https://github.com/o/r/pull/1",
            "title": "Test PR",
            "state": "OPEN",
            "owner": "o",
            "repo": "r",
        }
        assert len(result["conversation_comments"]) == 1
        assert result["conversation_comments"][0]["id"] == "c1"
        assert len(result["reviews"]) == 1
        assert len(result["review_threads"]) == 1

    def test_pagination_across_comments_pages(self, mod):
        page1 = _pr_page(
            comments_nodes=[{"id": "c1"}],
            has_next_c=True,
        )
        page2 = _pr_page(
            comments_nodes=[{"id": "c2"}],
        )
        with patch.object(mod, "gh_api_graphql", side_effect=[page1, page2]) as mock_gh:
            result = mod.fetch_all("o", "r", 1)

        assert len(result["conversation_comments"]) == 2
        assert mock_gh.call_count == 2
        # second call passes the cursor from page 1
        assert mock_gh.call_args_list[1][1]["comments_cursor"] == "c2"

    def test_independent_pagination_all_types(self, mod):
        page1 = _pr_page(
            comments_nodes=[{"id": "c1"}],
            reviews_nodes=[{"id": "r1"}],
            threads_nodes=[{"id": "t1"}],
            has_next_c=True,
            has_next_r=True,
            has_next_t=True,
        )
        page2 = _pr_page(
            comments_nodes=[{"id": "c2"}],
            reviews_nodes=[{"id": "r2"}],
            threads_nodes=[{"id": "t2"}],
            has_next_c=False,
            has_next_r=False,
            has_next_t=False,
        )
        with patch.object(mod, "gh_api_graphql", side_effect=[page1, page2]) as mock_gh:
            result = mod.fetch_all("o", "r", 1)

        assert len(result["conversation_comments"]) == 2
        assert len(result["reviews"]) == 2
        assert len(result["review_threads"]) == 2
        assert mock_gh.call_count == 2

    def test_empty_collections(self, mod):
        page = _pr_page()
        with patch.object(mod, "gh_api_graphql", return_value=page):
            result = mod.fetch_all("o", "r", 1)

        assert result["conversation_comments"] == []
        assert result["reviews"] == []
        assert result["review_threads"] == []
        assert result["pull_request"] is not None

    def test_null_nodes_handled_as_empty(self, mod):
        """GitHub API may return null for nodes; treat as empty list."""
        pr = {
            "number": 1,
            "url": "https://github.com/o/r/pull/1",
            "title": "Test PR",
            "state": "OPEN",
            "comments": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": None},
            "reviews": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": None},
            "reviewThreads": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": None},
        }
        page = {"data": {"repository": {"pullRequest": pr}}}
        with patch.object(mod, "gh_api_graphql", return_value=page):
            result = mod.fetch_all("o", "r", 1)

        assert result["conversation_comments"] == []
        assert result["reviews"] == []
        assert result["review_threads"] == []

    def test_pr_meta_captured_only_once(self, mod):
        page1 = _pr_page(comments_nodes=[{"id": "c1"}], has_next_c=True)
        page2 = _pr_page(comments_nodes=[{"id": "c2"}])
        with patch.object(mod, "gh_api_graphql", side_effect=[page1, page2]):
            result = mod.fetch_all("o", "r", 1)

        # pull_request metadata should be stable
        assert result["pull_request"]["number"] == 1
        assert result["pull_request"]["title"] == "Test PR"

    def test_graphql_errors_raised(self, mod):
        payload = {"errors": [{"message": "Something went wrong", "type": "NOT_FOUND"}]}
        with patch.object(mod, "gh_api_graphql", return_value=payload):
            with pytest.raises(RuntimeError, match="GitHub GraphQL errors"):
                mod.fetch_all("o", "r", 1)

    def test_graphql_errors_includes_details(self, mod):
        payload = {"errors": [{"message": "rate limit exceeded", "type": "RATE_LIMITED"}]}
        with patch.object(mod, "gh_api_graphql", return_value=payload):
            with pytest.raises(RuntimeError) as exc:
                mod.fetch_all("o", "r", 1)
            assert "rate limit" in str(exc.value)
            assert "RATE_LIMITED" in str(exc.value)

    def test_empty_errors_list_ignored(self, mod):
        """errors: [] should not raise."""
        page = _pr_page()
        page["errors"] = []
        with patch.object(mod, "gh_api_graphql", return_value=page):
            result = mod.fetch_all("o", "r", 1)
            assert result["pull_request"] is not None

    def test_stops_when_no_pages_remain(self, mod):
        page1 = _pr_page(comments_nodes=[{"id": "c1"}], reviews_nodes=[{"id": "r1"}], has_next_c=True)
        page2 = _pr_page(comments_nodes=[{"id": "c2"}], reviews_nodes=[{"id": "r2"}], has_next_r=True)
        page3 = _pr_page(comments_nodes=[{"id": "c3"}], reviews_nodes=[{"id": "r3"}])
        with patch.object(mod, "gh_api_graphql", side_effect=[page1, page2, page3]) as mock_gh:
            result = mod.fetch_all("o", "r", 1)
        assert len(result["conversation_comments"]) == 3
        assert len(result["reviews"]) == 3
        assert mock_gh.call_count == 3


# -- main ---------------------------------------------------------------------


class TestMain:
    """Tests for fetch_comments.main()."""

    def test_full_orchestration(self, mod):
        with (
            patch.object(mod, "_ensure_gh_authenticated") as mock_auth,
            patch.object(mod, "get_current_pr_ref", return_value=("o", "r", 1)) as mock_get_ref,
            patch.object(mod, "fetch_all", return_value={"pull_request": {}, "items": []}) as mock_fetch,
            patch("builtins.print") as mock_print,
        ):
            mod.main()

        mock_auth.assert_called_once()
        mock_get_ref.assert_called_once()
        mock_fetch.assert_called_once_with("o", "r", 1)
        mock_print.assert_called_once()
        # Verify the output is valid JSON
        import json
        args, _ = mock_print.call_args
        parsed = json.loads(args[0])
        assert parsed == {"pull_request": {}, "items": []}
