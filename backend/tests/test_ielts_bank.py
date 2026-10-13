"""Building the IELTS Task 2 topic bank from the btnotpt/ielts_task_2 dataset (Apache-2.0).

The raw topics are typed in by test takers: version tags, typos, Task 1 chart prompts,
broken encodings, truncated questions and many copies of the same question.
"""
from app.services.ielts_bank import accept_fix, clean_prompt, dedupe_variants, is_candidate


def test_clean_prompt_strips_version_tags_and_spaces():
    assert clean_prompt("  Some people  think X.\nDo you agree? v.3 ") == "Some people think X. Do you agree?"
    assert clean_prompt("Some people think X. Do you agree?v.12") == "Some people think X. Do you agree?"


def test_clean_prompt_capitalizes_first_letter():
    assert clean_prompt("in the future, nobody will buy books. Do you agree?") == \
        "In the future, nobody will buy books. Do you agree?"


GOOD = ("Some people believe that university education should be free for everyone. "
        "To what extent do you agree or disagree?")


def test_candidate_accepts_a_real_task2_question():
    assert is_candidate(GOOD)


def test_candidate_rejects_task1_chart_and_map_prompts():
    assert not is_candidate("The plans below show a public park when it first opened in 1920 and the same park "
                            "today. Summarise the information by selecting and reporting the main features.")
    assert not is_candidate("The bar chart shows the number of visitors to three museums between 2000 and 2010. "
                            "Summarise the information and make comparisons where relevant.")


def test_candidate_rejects_toefl_style_and_broken_text():
    assert not is_candidate("Some people prefer to live in a small town. Others prefer big cities. Which do you "
                            "prefer? Use specific reasons and examples to support your answer.")
    assert not is_candidate("Throughout the history, people dream to build a perfect society while they havenât "
                            "agreed how the ideal society would be like. What is the most important element?")


def test_candidate_rejects_truncated_and_title_like_topics():
    assert not is_candidate("Journalists are mainly responsible to bring this news to us but not all of them are "
                            "true to their responsi")
    assert not is_candidate("All education should be free")
    assert not is_candidate("Teenage Years Are The Happiest Period Of Life")


def test_dedupe_keeps_the_most_written_variant():
    a = ("Some governments spend a lot of money on exploring space. Some feel that this investment is justified "
         "while others think the money should be spent on public services. Discuss both views and give your opinion.")
    b = ("Some governments spend a lot of money on exploring space. some feel that this investment is justified "
         "while others think that money should be spent on public services like healthcare. Discuss both views and "
         "give your own opinion.")
    other = GOOD
    kept = dedupe_variants({a: 3, b: 9, other: 1})
    assert kept == {b: 12, other: 1}


def test_accept_fix_takes_spelling_fixes_only():
    orig = "Many people belive that women make better parents than men. To what extent do you agree or disagree?"
    fixed = "Many people believe that women make better parents than men. To what extent do you agree or disagree?"
    assert accept_fix(orig, fixed) == fixed


def test_accept_fix_rejects_a_rewrite():
    orig = "Many people belive that women make better parents than men. To what extent do you agree or disagree?"
    rewrite = "Should fathers stay at home with children while mothers go to work? Discuss."
    assert accept_fix(orig, rewrite) is None
    assert accept_fix(orig, "") is None
