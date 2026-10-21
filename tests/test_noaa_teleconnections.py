from tools.import_noaa_teleconnections import parse_monthly


def test_parse_monthly_records():
    line = '2025 ' + ' '.join(str(i) for i in range(1, 13))
    rows = parse_monthly('NOAA index\n' + line)
    assert len(rows) == 12
    assert rows[0] == {'month': '2025-01', 'value': 1.0}
    assert rows[-1] == {'month': '2025-12', 'value': 12.0}


def test_missing_values_not_treated_as_observations():
    line = '2025 ' + ' '.join(['-99.9'] + ['0.2'] * 11)
    rows = parse_monthly(line)
    assert len(rows) == 11
    assert rows[0]['month'] == '2025-02'


def test_invalid_rows_are_ignored():
    assert parse_monthly('2000 1 2 3\nfooter') == []
