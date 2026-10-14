"""Offline provider so the demo runs without an API key.

It ignores the prompt text and builds plausible, correct content from the request metadata.
"""

import json
import random
from collections.abc import Callable
from fractions import Fraction

from app.llm.provider import CompletionRequest
from app.models import (
    BarChart,
    CurriculumItem,
    MathCheck,
    NumberLine,
    Question,
    Rectangle,
    SectionDefinition,
    StudentLevel,
)

F, C, E = StudentLevel.FOUNDATION, StudentLevel.CORE, StudentLevel.EXTENSION


def frac(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    whole, rest = divmod(value.numerator, value.denominator)
    if whole and rest:
        return f"{whole} {rest}/{value.denominator}"
    return f"{value.numerator}/{value.denominator}"


def q(prompt: str, answer: str, working: str, expression: str, expected: str, **kw) -> Question:
    return Question(
        prompt=prompt,
        answer=answer,
        working=working,
        check=MathCheck(expression=expression, expected=expected),
        **kw,
    )


def gen_add_sub(rng: random.Random, tier: StudentLevel) -> Question:
    if tier == F:
        a, b = rng.randint(24, 58), rng.randint(17, 39)
        return q(f"{a} + {b} = ?", str(a + b), f"{a} + {b}: add the ones, regroup, then add the "
                 f"tens. {a} + {b} = {a + b}", f"{a}+{b}", str(a + b))
    if tier == C:
        a, b = rng.randint(312, 645), rng.randint(128, 289)
        return q(f"{a} − {b} = ?", str(a - b), f"Regroup a ten (and a hundred if needed): "
                 f"{a} − {b} = {a - b}", f"{a}-{b}", str(a - b))
    a, b, c = rng.randint(240, 420), rng.randint(115, 180), rng.randint(90, 160)
    return q(f"The Box Hill library had {a} books. It received {b} new books and then lent out "
             f"{c}. How many books are on the shelves now?", f"{a + b - c} books",
             f"{a} + {b} = {a + b}; {a + b} − {c} = {a + b - c}", f"{a}+{b}-{c}", str(a + b - c))


def gen_times_facts(rng: random.Random, tier: StudentLevel) -> Question:
    a, b = rng.choice([2, 3, 4, 5, 10]), rng.randint(3, 10)
    if tier == F:
        return q(f"{a} × {b} = ?", str(a * b), f"Skip count by {a}, {b} times: {a * b}",
                 f"{a}*{b}", str(a * b))
    if tier == C:
        return q(f"{a * b} ÷ {a} = ?", str(b), f"Think: {a} × ? = {a * b}. The answer is {b}.",
                 f"{a * b}/{a}", str(b))
    return q(f"Mia packs {b} lunch boxes with {a} strawberries in each, then eats {a} "
             f"strawberries herself. How many strawberries did she use altogether?",
             f"{a * b + a} strawberries", f"{a} × {b} = {a * b}; {a * b} + {a} = {a * b + a}",
             f"{a}*{b}+{a}", str(a * b + a))


def gen_length(rng: random.Random, tier: StudentLevel) -> Question:
    if tier == F:
        m = rng.randint(2, 9)
        return q(f"How many centimetres are in {m} metres?", f"{m * 100} cm",
                 f"1 m = 100 cm, so {m} m = {m} × 100 = {m * 100} cm", f"{m}*100", str(m * 100))
    if tier == C:
        m = rng.randint(1, 6)
        return q(f"Write {m}.5 m in centimetres.", f"{m * 100 + 50} cm",
                 f"{m}.5 × 100 = {m * 100 + 50} cm", f"{m}.5*100", str(m * 100 + 50))
    m, cut = rng.randint(2, 4), rng.randint(35, 85)
    return q(f"A ribbon is {m} m long. Sam cuts off {cut} cm. How many centimetres are left?",
             f"{m * 100 - cut} cm", f"{m} m = {m * 100} cm; {m * 100} − {cut} = {m * 100 - cut} cm",
             f"{m}*100-{cut}", str(m * 100 - cut))


def gen_equivalent_fractions(rng: random.Random, tier: StudentLevel) -> Question:
    if tier == F:
        n = rng.choice([2, 3, 4])
        return q(f"Complete: 1/2 = ?/{2 * n}", str(n), f"Multiply top and bottom by {n}: "
                 f"1/2 = {n}/{2 * n}", f"1*{2 * n}/2", str(n),
                 diagram=NumberLine(start=0, end=1, step=1 / (2 * n), marks=[0.5], labels=["1/2"]))
    if tier == C:
        n = rng.choice([2, 3, 4])
        return q(f"Complete: 2/3 = ?/{3 * n}", str(2 * n), f"Multiply top and bottom by {n}: "
                 f"2/3 = {2 * n}/{3 * n}", f"2*{3 * n}/3", str(2 * n))
    return q("Which is larger, 3/4 or 5/8? By how much?", "3/4 is larger by 1/8",
             "3/4 = 6/8, and 6/8 − 5/8 = 1/8", "3/4-5/8", "1/8")


def gen_multiply(rng: random.Random, tier: StudentLevel) -> Question:
    a, b = rng.randint(12, 48), rng.randint(3, 9)
    if tier == F:
        a = rng.choice([11, 12, 21, 22, 31])
        b = rng.randint(2, 4)
    tens, ones = divmod(a, 10)
    working = f"{a} × {b} = {tens * 10} × {b} + {ones} × {b} = {tens * 10 * b} + {ones * b} " \
              f"= {a * b}"
    if tier == E:
        return q(f"Tickets to Melbourne Zoo cost ${a} each. How much do {b} tickets cost?",
                 f"${a * b}", working, f"{a}*{b}", str(a * b))
    return q(f"{a} × {b} = ?", str(a * b), working, f"{a}*{b}", str(a * b))


def gen_rectangle(rng: random.Random, tier: StudentLevel) -> Question:
    w, h = rng.randint(4, 12), rng.randint(2, 8)
    if tier == F:
        return q(f"Find the perimeter of a rectangle {w} cm long and {h} cm wide.",
                 f"{2 * (w + h)} cm", f"2 × ({w} + {h}) = {2 * (w + h)} cm", f"2*({w}+{h})",
                 str(2 * (w + h)), diagram=Rectangle(width=w, height=h))
    if tier == C:
        return q(f"Find the area of a rectangle {w} cm long and {h} cm wide.", f"{w * h} cm²",
                 f"{w} × {h} = {w * h} cm²", f"{w}*{h}", str(w * h),
                 diagram=Rectangle(width=w, height=h))
    return q(f"A rectangular garden bed has an area of {w * h} m² and is {h} m wide. "
             f"How long is it, and what is its perimeter?",
             f"{w} m long, perimeter {2 * (w + h)} m",
             f"Length = {w * h} ÷ {h} = {w} m; perimeter = 2 × ({w} + {h}) = {2 * (w + h)} m",
             f"2*({w * h}/{h}+{h})", str(2 * (w + h)))


def gen_same_denominator(rng: random.Random, tier: StudentLevel) -> Question:
    d = rng.choice([5, 6, 8, 10])
    if tier == F:
        a, b = 1, rng.randint(1, d - 2)
        s = Fraction(a + b, d)
        return q(f"{a}/{d} + {b}/{d} = ?", frac(s), f"Add the numerators: {a} + {b} = {a + b}, "
                 f"so the answer is {a + b}/{d} = {frac(s)}", f"{a}/{d}+{b}/{d}", str(s),
                 diagram=NumberLine(start=0, end=1, step=1 / d, marks=[(a + b) / d]))
    if tier == C:
        whole, a, b = rng.randint(1, 3), rng.randint(1, d - 1), rng.randint(1, d - 1)
        start = Fraction(whole * d + a, d)
        result = start - Fraction(b, d)
        return q(f"{whole} {a}/{d} − {b}/{d} = ?", frac(result),
                 f"{whole} {a}/{d} = {start.numerator}/{d}; {start.numerator}/{d} − {b}/{d} = "
                 f"{start.numerator - b}/{d} = {frac(result)}", f"{start.numerator}/{d}-{b}/{d}",
                 str(result))
    a, b = rng.randint(2, 3), rng.randint(2, 3)
    left = Fraction(d - a - b, d)
    return q(f"A pizza is cut into {d} equal slices. Leo eats {a}/{d} and Ava eats {b}/{d}. "
             "What fraction of the pizza is left?", frac(left),
             f"Eaten: {a + b}/{d}. Left: {d}/{d} − {a + b}/{d} = {frac(left)}",
             f"1-{a}/{d}-{b}/{d}", str(left))


def gen_decimals(rng: random.Random, tier: StudentLevel) -> Question:
    if tier == F:
        a, b = rng.randint(1, 6) / 10, rng.randint(11, 39) / 100
        return q(f"{a:g} + {b:g} = ?", f"{a + b:.2f}", f"Line up the decimal points: "
                 f"{a:.2f} + {b:.2f} = {a + b:.2f}", f"{a:g}+{b:g}", f"{a + b:.2f}")
    if tier == C:
        a, b = rng.randint(101, 399) / 100, rng.randint(1001, 2999) / 1000
        return q(f"{a:.2f} + {b:.3f} = ?", f"{a + b:.3f}", f"{a:.3f} + {b:.3f} = {a + b:.3f}",
                 f"{a:.2f}+{b:.3f}", f"{a + b:.3f}")
    return q("Order 0.305, 0.35 and 0.053 from smallest to largest, then find the difference "
             "between the largest and smallest.", "0.053, 0.305, 0.35; difference 0.297",
             "Compare tenths first: 0.0 < 0.3; then hundredths: 0.30 < 0.35. 0.35 − 0.053 = 0.297",
             "0.35-0.053", "0.297")


def gen_column_graph(rng: random.Random, tier: StudentLevel) -> Question:
    sports = ["AFL", "Soccer", "Netball", "Cricket"]
    values = [rng.randint(3, 12) for _ in sports]
    chart = BarChart(title="Favourite sport in 5B", categories=sports, values=values,
                     y_label="Students")
    if tier == F:
        return q("How many students chose Netball?", str(values[2]), "Read the top of the "
                 "Netball column against the scale.", str(values[2]), str(values[2]),
                 diagram=chart)
    if tier == C:
        hi, lo = max(values), min(values)
        return q("How many more students chose the most popular sport than the least popular?",
                 str(hi - lo), f"Most popular: {hi}; least popular: {lo}; {hi} − {lo} = {hi - lo}",
                 f"{hi}-{lo}", str(hi - lo), diagram=chart)
    total = sum(values)
    return q("How many students were surveyed altogether?", str(total),
             " + ".join(map(str, values)) + f" = {total}", "+".join(map(str, values)), str(total),
             diagram=chart)


def gen_related_denominators(rng: random.Random, tier: StudentLevel) -> Question:
    d = rng.choice([3, 4, 5, 6])
    a, b = rng.randint(1, d - 1), rng.randint(1, 2 * d - 1)
    if tier == F:
        s = Fraction(a, d) + Fraction(1, 2 * d)
        return q(f"{a}/{d} + 1/{2 * d} = ?", frac(s), f"{a}/{d} = {2 * a}/{2 * d}; "
                 f"{2 * a}/{2 * d} + 1/{2 * d} = {frac(s)}", f"{a}/{d}+1/{2 * d}", str(s))
    if tier == C:
        s = Fraction(b, 2 * d) + Fraction(a, d)
        return q(f"{b}/{2 * d} + {a}/{d} = ?", frac(s), f"Rename {a}/{d} as {2 * a}/{2 * d}; "
                 f"{b + 2 * a}/{2 * d} = {frac(s)}", f"{b}/{2 * d}+{a}/{d}", str(s))
    left = 1 - Fraction(1, d) - Fraction(1, 2 * d)
    return q(f"Noah spends 1/{d} of his pocket money on a book and 1/{2 * d} on snacks. "
             "What fraction does he have left?", frac(left),
             f"1/{d} = 2/{2 * d}; spent 3/{2 * d}; left {frac(left)}",
             f"1-1/{d}-1/{2 * d}", str(left))


def gen_percentages(rng: random.Random, tier: StudentLevel) -> Question:
    amount = rng.choice([40, 60, 80, 120, 160, 200])
    if tier == F:
        return q(f"What is 50% of ${amount}?", f"${amount // 2}", f"50% is one half: "
                 f"{amount} ÷ 2 = {amount // 2}", f"50/100*{amount}", str(amount // 2))
    if tier == C:
        p = rng.choice([10, 25])
        value = Fraction(p, 100) * amount
        return q(f"What is {p}% of {amount} kg?", f"{frac(value)} kg",
                 f"{p}% = {p}/100, so {p}/100 × {amount} = {frac(value)}",
                 f"{p}/100*{amount}", str(value))
    off = Fraction(15, 100) * amount
    return q(f"A pair of runners costs ${amount}. In a sale they are 15% off. What is the sale "
             "price?", f"${frac(amount - off)}", f"10% = ${amount / 10:g}, 5% = "
             f"${amount / 20:g}, so 15% = ${frac(off)}; ${amount} − ${frac(off)} = "
             f"${frac(amount - off)}", f"{amount}-15/100*{amount}", str(amount - off))


def gen_integers(rng: random.Random, tier: StudentLevel) -> Question:
    if tier == F:
        n = -rng.randint(2, 6)
        return q("What number is shown by the dot on the number line?", str(n),
                 f"Count {abs(n)} steps left of zero: {n}", str(n), str(n),
                 diagram=NumberLine(start=-8, end=8, step=1, marks=[n]))
    if tier == C:
        t, rise = -rng.randint(2, 6), rng.randint(5, 10)
        return q(f"At 6 am in Ballarat it was {t}°C. By noon the temperature rose {rise}°C. "
                 "What was the temperature at noon?", f"{t + rise}°C",
                 f"{t} + {rise} = {t + rise}", f"{t}+{rise}", str(t + rise))
    a, b = rng.randint(3, 9), -rng.randint(4, 9)
    return q(f"What is the difference between {a} and {b}?", str(a - b),
             f"Distance from {b} to 0 is {abs(b)}, from 0 to {a} is {a}: {abs(b)} + {a} = {a - b}",
             f"{a}-({b})", str(a - b))


def gen_mean(rng: random.Random, tier: StudentLevel) -> Question:
    n = 4
    mean = rng.randint(5, 12)
    values = [mean + d for d in rng.choice([[-2, 1, 3, -2], [-3, 0, 2, 1], [1, -1, 4, -4]])]
    listed = ", ".join(map(str, values))
    if tier == F:
        return q(f"Find the mean of {listed}.", str(mean),
                 f"Total = {sum(values)}; {sum(values)} ÷ {n} = {mean}",
                 f"({'+'.join(map(str, values))})/{n}", str(mean))
    if tier == C:
        return q(f"Find the range of {listed}.", str(max(values) - min(values)),
                 f"{max(values)} − {min(values)} = {max(values) - min(values)}",
                 f"{max(values)}-{min(values)}", str(max(values) - min(values)))
    first = values[:3]
    missing = n * mean - sum(first)
    return q(f"Ella's mean score over {n} spelling tests is {mean}. Her first three scores were "
             f"{', '.join(map(str, first))}. What did she score in the fourth test?", str(missing),
             f"Total needed = {n} × {mean} = {n * mean}; {n * mean} − {sum(first)} = {missing}",
             f"{n}*{mean}-({'+'.join(map(str, first))})", str(missing))


GENERATORS: dict[str, Callable[[random.Random, StudentLevel], Question]] = {
    "VC2M3N03": gen_add_sub,
    "VC2M3N05": gen_times_facts,
    "VC2M3M03": gen_length,
    "VC2M4N04": gen_equivalent_fractions,
    "VC2M4N07": gen_multiply,
    "VC2M4M02": gen_rectangle,
    "VC2M5N05": gen_same_denominator,
    "VC2M5N06": gen_decimals,
    "VC2M5M02": gen_rectangle,
    "VC2M5ST01": gen_column_graph,
    "VC2M6N04": gen_related_denominators,
    "VC2M6N07": gen_percentages,
    "VC2M6N01": gen_integers,
    "VC2M6ST01": gen_mean,
}

SECTION_TIERS: dict[str, tuple[list[StudentLevel], bool]] = {
    "worked_examples": ([F, C, E], False),
    "practice": ([F, F, F, C, C, C, E, E, E], True),
    "quiz": ([F, C, C, E], False),
    "homework": ([F, C, C, C, E, E], False),
}


def _markdown(section: SectionDefinition, item: CurriculumItem, meta: dict) -> str:
    points = "\n".join(f"- {p}" for p in item.teaching_points)
    if section.id == "warm_up":
        body = (
            "## Quick review (5-8 min)\n"
            f"Ask these on the whiteboard before starting **{item.topic.lower()}**:\n"
            "1. A prerequisite fact from last week's lesson\n"
            "2. A place value or times-table question linked to today's topic\n"
            "3. One question where students explain their thinking aloud\n\n"
            "**Readiness check:** students who hesitate on question 2 should sit near the "
            "teacher during the explanation."
        )
    elif section.id == "teach":
        body = (
            "## Learning intention\n"
            f"We are learning to: {item.summary[0].lower() + item.summary[1:]}\n\n"
            "## Success criteria\n"
            "- I can explain the method in my own words\n"
            "- I can solve a question without looking at the example\n"
            "- I can check my answer is reasonable\n\n"
            "## Key teaching points\n"
            f"{points}\n\n"
            "## Common misconceptions\n"
            "- Applying the rule without understanding why it works: ask students to draw a model\n"
            "- Skipping the estimate: always ask \"Is this answer sensible?\"\n\n"
            "## Timing\n"
            "- Explanation with a concrete model: 10 min\n"
            "- Worked examples: 10 min\n"
            "- Tiered practice: 20 min\n"
            "- Exit quiz: 5 min"
        )
    elif section.id == "parent_note":
        if "chinese" in meta.get("parent_language", "").lower():
            body = (
                f"各位家长好！今天的数学课我们学习了 **{item.topic}**"
                f"（维州课程 Level {item.level}，{item.code}）。\n\n"
                "这个知识点是后续学习的重要基础。孩子们先复习了相关的旧知识，再通过例题和分层练习"
                "巩固新方法，最后做了一个小测检查掌握情况。\n\n"
                "**在家可以这样练习：** 在购物或做饭时，请孩子用今天学到的方法算一算，"
                "并说出自己的思路。每天 10 分钟就很有帮助。\n\n"
                "如有任何问题，欢迎随时联系我们。"
            )
        else:
            body = (
                f"Dear parents, today we learned **{item.topic}** (Victorian Curriculum "
                f"Level {item.level}, {item.code}). Students reviewed earlier skills, worked "
                "through examples together and practised at their own level.\n\n"
                "**At home:** ask your child to explain today's method using a real-life "
                "example, such as shopping or cooking. Ten minutes a day makes a difference."
            )
    else:
        body = f"## {section.title}\n{item.summary}"

    if meta.get("feedback"):
        body += f"\n\n_Revised following teacher feedback: {meta['feedback']}_"
    return body


def _questions(section: SectionDefinition, item: CurriculumItem, meta: dict) -> str:
    generator = GENERATORS.get(item.code, gen_add_sub)
    tiers, tiered = SECTION_TIERS.get(section.id, ([C, C, C, C], False))
    seed = f"{item.code}:{section.id}:{meta.get('feedback') or ''}"
    rng = random.Random(seed)
    questions = []
    for tier in tiers:
        question = generator(rng, tier)
        question.tier = tier if tiered else None
        questions.append(question.model_dump(mode="json", exclude={"check_result"}))
    return json.dumps({"questions": questions}, ensure_ascii=False)


class MockProvider:
    name = "mock"

    async def complete(self, request: CompletionRequest) -> str:
        meta = request.meta
        if meta.get("kind") == "fix":
            question: Question = meta["question"]
            computed = meta.get("computed")
            fixed = question.model_copy(deep=True)
            if computed is not None and fixed.check is not None:
                fixed.check.expected = computed
                fixed.answer = computed
            return fixed.model_dump_json(exclude={"check_result"})

        section: SectionDefinition = meta["section"]
        item: CurriculumItem = meta["item"]
        if section.output_type == "questions":
            return _questions(section, item, meta)
        return _markdown(section, item, meta)
