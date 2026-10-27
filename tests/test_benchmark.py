import importlib.util


def test_benchmark_cases_cover_all_six_directions_with_shared_meaning():
    assert importlib.util.find_spec('babblet.benchmark'), 'Benchmark harness must exist'
    from babblet.benchmark import cases, summarize
    items = cases()
    assert {(c['source'], c['target']) for c in items} == {
        ('en','he'), ('en','ru'), ('he','en'), ('he','ru'), ('ru','en'), ('ru','he')}
    assert len(items) >= 18
    summary = summarize([{'seconds': 1, 'error': None}, {'seconds': 3, 'error': None},
                         {'seconds': 0.1, 'error': 'failed'}])
    assert summary['completed'] == 2
    assert summary['errors'] == 1
    assert summary['median_seconds'] == 2
