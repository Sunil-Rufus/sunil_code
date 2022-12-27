"""
Heavily inspired by dfm/cv/scripts/render.py
"""

import importlib.util
import inspect
import json
import os
from datetime import date
from operator import itemgetter

import requests
from bs4 import BeautifulSoup

import cv

GOOGLE_SCHOLAR = False
FORMAT_STYLE = "latex"
FIRSTNAME = "Arjun"
LASTNAME = "Savel"

cv_root = inspect.getfile(cv).split("cv")[0]
data_path = os.path.join(cv_root, "data")
supp_tex_path = os.path.join(cv_root, "supp_tex")

cv_path = inspect.getfile(cv).split("__init")[0]
here = os.path.join(cv_path, "scripts")
spec = importlib.util.spec_from_file_location(
    "utf8totex", os.path.join(here, "utf8totex.py")
)
utf8totex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utf8totex)

with open(os.path.join(data_path, "journal_map.json")) as f:
    JOURNAL_MAP = json.load(f)

with open(os.path.join(data_path, "in_press.txt")) as f:
    in_press = f.readlines()


def write_tex_file(filename, contents):
    with open(os.path.join(supp_tex_path, filename), "w") as f:
        f.write("\n\n".join(contents))


def check_preprint(pub):
    """
    checks whether a publication is just a preprint.
    """
    return "ArXiv" in pub["pub"] or "arXiv" in pub["pub"]


def check_preprint_match(ref1, ref2):
    """
    Checks whether two references have the same title.
    """
    return (
        check_preprint(ref2)
        and ref["title"] == ref2["title"]
        and not check_preprint(ref1)
    )


def match_arxiv(ref, other_ref, i, ref_list):
    if check_preprint_match(ref, other_ref):
        ref["arxiv"] = other_ref["arxiv"]
        ref["citations"] += other_ref["citations"]
        del ref_list[i]


def check_duplicates(ref_list):
    """
    Checks a given reference list for duplicates. If there are duplicates...joins them!
    todo: make some other check for similarity in author list.
    todo: title similarity check should be inclusive of weird character changes.
    """
    for ref in ref_list:
        for i, other_ref in enumerate(ref_list.copy()):
            match_arxiv(ref, other_ref, i, ref_list)

    return ref_list


def check_inpress(pub):
    """
    Checks whether a given paper is in the inpress data file.
    If so, it should go under "peer-reviewed" in the CV — with the
    caveat that it's in press.

    Inputs
    -------
    :pub: (dict) publication object. Needs to have 'title' key.
    """

    # # read in the in press data

    for i, press in enumerate(in_press):
        in_press[i] = press.split("\n")[0]

    if pub["title"] in in_press:
        pub["doctype"] = "article"
        return True
    # more general case
    URL = "http://arxiv.org/abs/" + pub["arxiv"]

    page = requests.get(URL)

    soup = BeautifulSoup(page.content, "html.parser")
    results = soup.find(class_="comments")
    if results.text and "accepted" in results.text.lower():
        pub["doctype"] = "article"
    return results.text and "accepted" in results.text.lower()


def add_student_attribution(pub, last_name, start_year, end_year):
    """
    Adds an asterisk to a student's name.
    """
    pub_year = eval(pub["year"])
    if start_year <= pub_year and end_year >= pub_year:
        # todo: fix, as will catch overlapping last names.
        ns = [i for i in range(len(pub["authors"])) if last_name in pub["authors"][i]]
        if len(ns) > 0:
            n = ns[0]
            pub["authors"][n] = "*" + pub["authors"][n]
    return pub


def format_for_students(pub):
    """
    formats a publication to add students in first 5 authors.
    """

    # Opening JSON file.
    f = open(os.path.join(data_path, "students.json"))

    # returns JSON object as a dictionary
    data = json.load(f)
    f.close()
    student_names = data.keys()

    for student_name in student_names:
        last_name, first_name = student_name.split(", ")
        start_year, end_year = data[student_name].split(", ")
        start_year, end_year = eval(start_year), eval(end_year)

        pub = add_student_attribution(pub, last_name, start_year, end_year)

    return pub


def format_index(ind):
    if FORMAT_STYLE == "latex":
        return "\\item[{{\\color{{numcolor}}\\scriptsize{0}}}] ".format(ind)
    return str(ind)


def format_title(title):
    if FORMAT_STYLE == "latex":
        return title.replace("{\\&}amp;", "\&")  # for latex literal interp.
    return title.replace("{\\&}amp;", "&")


def add_etal(string):
    """
    adds the et al!
    """
    if FORMAT_STYLE == "latex":
        string += "\\etal"
    else:
        string += "et al. "

    return string


def add_other_coauthors(string, others):
    if FORMAT_STYLE == "latex":
        string += "\\ ({{{0}}} other co-authors, ".format(others)
        string += "incl.\\ \\textbf{{{0}}, {{1}}})".format(LASTNAME, FIRSTNAME)
    else:
        string += "({{{0}}} other co-authors, ".format(others)
        string += f"incl. {LASTNAME}, {FIRSTNAME})"
    return string


def format_authors(authors, cutoff_length, short, n):
    """
    fix how the authors are formatted.
    """
    fmt = ""

    if len(authors) > cutoff_length:
        fmt += "; ".join(pub["authors"][:cutoff_length])

        fmt = add_etal(fmt)

        if n >= cutoff_length - 1 and not short:
            others = len(pub["authors"]) - (cutoff_length - 1)

            fmt = add_other_coauthors(fmt, others)

    elif len(pub["authors"]) > 1:
        fmt += "; ".join(pub["authors"][:-1])
        fmt += "; \\& " + pub["authors"][-1]
    else:
        fmt += pub["authors"][0]

    fmt += " {0}".format(pub["year"])
    return fmt


def format_doi(doi, pub_title):
    fmt = ""
    if FORMAT_STYLE == "latex":
        if doi is not None:
            fmt += ", \\doi{{{0}}}{{{1}}}".format(doi, pub_title)
        else:
            fmt += ", \\emph{{{0}}}".format(pub_title)
    else:
        # can't hyperlink text?
        fmt += ", {0}".format(pub_title)

    return fmt


def format_pub(args):
    ind, pub, short = args
    pub = pub.copy()

    fmt = format_index(ind)
    n = [i for i in range(len(pub["authors"])) if LASTNAME in pub["authors"][i]][0]
    pub["authors"][n] = "\\textbf{{{0}}, {{1}}}".format(LASTNAME, FIRSTNAME)

    pub = format_for_students(pub)

    pub_title = format_title(pub["title"])

    if short:
        cutoff_length = 1
    else:
        cutoff_length = 4

    if len(pub["authors"]) > cutoff_length:
        fmt += "; ".join(pub["authors"][:cutoff_length])
        fmt += " \\etal "
        if n >= cutoff_length - 1 and not short:
            others = len(pub["authors"]) - (cutoff_length - 1)
            fmt += "\\ ({{{0}}} other co-authors, ".format(others)
            fmt += "incl.\\ \\textbf{Savel, Arjun})"
    elif len(pub["authors"]) > 1:
        fmt += "; ".join(pub["authors"][:-1])
        fmt += "; \\& " + pub["authors"][-1]
    else:
        fmt += pub["authors"][0]

    fmt += format_authors(pub["authors"], cutoff_length, short, n)
    fmt += format_doi(pub["doi"], pub_title)

    if not pub["pub"] in [None, "ArXiv e-prints"]:
        fmt += ", " + JOURNAL_MAP.get(pub["pub"].strip("0123456789# "), pub["pub"])
        if short:
            fmt += "\\ "

    if pub["volume"] is not None and not short:
        fmt += ", {{{0}}}".format(pub["volume"])

    if pub["page"] is not None and not short:
        fmt += ", {0}".format(pub["page"])

    if (pub["arxiv"] is not None and not short) or pub["pub"] in [
        None,
        "ArXiv e-prints",
    ]:
        fmt += " (\\arxiv{{{0}}})".format(pub["arxiv"])

    if check_inpress(pub):
        # need to add caveat!
        fmt += " (in press)"

    if pub["url"] is not None and pub["citations"] == 1:
        fmt += " [\\href{{{0}}}{{{1} citation}}]".format(pub["url"], pub["citations"])

    elif pub["url"] is not None and pub["citations"] > 1:
        fmt += " [\\href{{{0}}}{{{1} citations}}]".format(pub["url"], pub["citations"])

    return fmt


if __name__ == "__main__":

    if GOOGLE_SCHOLAR:
        with open(os.path.join(data_path, "google_scholar_scrape.json"), "r") as f:
            pubs = json.load(f)
    else:
        with open(os.path.join(data_path, "ads_scrape.json"), "r") as f:
            pubs = json.load(f)

    pubs = sorted(pubs, key=itemgetter("pubdate"), reverse=True)

    # want to include articles and preprints, but not Zenodo repos.
    pubs = [
        p
        for p in pubs
        if (
            p["doctype"] in ["article", "eprint"]
            and p["pub"] != "Zenodo Software Release"
        )
    ]

    # want to include in press articles under refereed
    for pub in pubs:
        check_inpress(pub)

    ref_list = [p for p in pubs if p["doctype"] == "article"]
    unref_list = [p for p in pubs if p["doctype"] == "eprint"]

    ref_list = check_duplicates(ref_list)
    unref_list = check_duplicates(unref_list)

    # Compute citation stats
    npapers = len(ref_list)
    nfirst = sum(1 for p in pubs if LASTNAME in p["authors"][0])
    cites = sorted((p["citations"] for p in pubs), reverse=True)
    ncitations = sum(cites)
    hindex = sum(c > i for i, c in enumerate(cites))

    with open(os.path.join(supp_tex_path, "n_first_submit.tex")) as f:
        nfirst_submit = eval(f.readlines()[0].split("\n")[0])

    summary = (
        "citations: {1} / "
        "h-index: {2} / "
        "{3} first-author refereed, {4} under review  ({0})"
    ).format(date.today(), ncitations, hindex, nfirst, nfirst_submit)
    with open(os.path.join(supp_tex_path, "pubs_summary.tex"), "w") as f:
        f.write(summary)

    # todo: refactor. this is gross. maybe some kind of partial func.
    short = [False for i in range(len(ref_list))]

    ref = list(map(format_pub, zip(range(len(ref_list), 0, -1), ref_list, short)))
    unref = list(map(format_pub, zip(range(len(unref_list), 0, -1), unref_list, short)))

    # todo: refactor. this is gross.
    short = [True for i in range(len(ref))]
    ref_short = list(map(format_pub, zip(range(len(ref_list), 0, -1), ref_list, short)))
    unref_short = list(
        map(format_pub, zip(range(len(unref_list), 0, -1), unref_list, short))
    )

    # for now, written to tex files even if they're gonna be used in a text file.
    write_tex_file("pubs_ref.tex", ref)
    write_tex_file("pubs_unref.tex", unref)
    write_tex_file("pubs_ref_short.tex", ref_short)
    write_tex_file("pubs_unref_short.tex", unref_short)
