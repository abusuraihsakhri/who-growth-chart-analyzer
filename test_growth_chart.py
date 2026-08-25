import growth_chart as m
def test_smoke():
    r=m.assess_row({'value':10})
    assert isinstance(r, dict)
