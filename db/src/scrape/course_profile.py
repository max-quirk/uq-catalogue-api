import src.scrape.helpers as helpers
import src.settings as settings
import pandas as pd
import re


def course_profile(course_code, course_profile_id):
    """
    Scrapes a course profile
    :return: Dict Object, containing course profile details
    """
    base_url = (
        f"https://www.courses.uq.edu.au/student_section_loader.php?section=5&profileId={course_profile_id}"
    )
    try:
        all_tables = pd.read_html(base_url, match='Assessment Task')

    except ValueError:
        return
    # gets tables containing desired information
    all_tables = all_tables[2:]
    for i, table in enumerate(all_tables):
        print(table)
        if len(table.columns) != 4:
            del all_tables[i]

    assessments = []
    for table in all_tables:
        table_length = table.shape[0] - 1
        i = 1

        while i <= table_length:

            name = table.at[i, 0]
            print(splitName(name))
            due_date = table.at[i, 1]
            weighting = table.at[i, 2]
            learning_obj = table.at[i, 3]

            assessment = {
                'course_code': course_code,
                'name': splitName(name),
                'due_date': due_date,
                'weighting': weighting,
                'learning_obj': learning_obj
            }
            assessments.append(assessment)

            i += 1

    return assessments


def splitName(name):  # Separates assessment type from assessment name
    for index, letter in enumerate(name):
        try:
            if letter.islower() and name[index + 1].isupper() \
                    or letter == ')' and name[index + 1].isupper():
                return name[index+1:]
        except IndexError:
            return name
    return name


if __name__ == '__main__':
    x = course_profile('STAT1301', '93044')
    print(x)
