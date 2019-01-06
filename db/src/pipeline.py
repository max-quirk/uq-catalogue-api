"""
Migrate
"""
from tqdm import tqdm
import src.database as database
import src.scrape as scrape
import src.settings as settings


class Pipeline:
    """
    Utility class for ETL pipeline
    """

    def __init__(self):
        self._db = database.Db(detailed=False)
        self._db.connect(
            settings.DATABASE["NAME"],
            settings.DATABASE["USER"],
            settings.DATABASE["PASSWORD"],
            settings.DATABASE["HOST"],
        )
        self._logfile = None

        # development use only
        # self._dev_course_count = 0
        # self._dev_plan_count = 0

    def reset(self):
        """
        Clears DB, truncating each table in order of dependency
        :return: None
        """
        check = input(
            "Wipe database and start over (WARNING: this will remove all existing data in the database)? [Y/n] "
        )
        if check.lower() != "y":
            return

        queries = [
            "DELETE from plan_course_list",
            "DELETE from program_course_list",
            "DELETE from incompatible_courses",
            "DELETE from course",
            "DELETE from plan",
            "DELETE from program",
        ]

        for sql in queries:
            self._db.commit(sql)

    def run(self):
        """
        Runs the pipeline
        :return: None
        """
        self._logfile = open("incompatible_courses.txt", "w")
        program_list = scrape.catalogue()
        print(program_list)

        print("\n************* INITIALISING PIPELINE *************\n")

        for program_code in program_list:
            print("\nLOADING PROGRAM:", program_code)
            print("\tScraping program...")
            program = self.add_program(program_code)
            print("\tBuilding course list...")
            self.add_program_course_list(program_code)

            if program is None:
                return

            for plan in program["plan_list"]:
                # if self._dev_plan_count > 1:
                # return
                # self._dev_plan_count += 1
                print("\nLOADING PLAN:", plan["plan_code"])

                print("\tScraping plan...")
                plan = self.add_plan(plan["plan_code"], plan["title"])
                print("\tBuilding course list... Size:", len(plan["course_list"]))
                self.add_plan_course_list(plan["plan_code"], plan["course_list"])

        print("\n************* PIPELINE COMPLETE *************\n")

    def add_program(self, program_code):
        """

        :param program_code: String, 4 digit code of desired program
        :return:
        """
        sql = (
            """
            SELECT program_code
            FROM program
            WHERE program_code = '%s'
            """
            % program_code
        )
        res = self._db.select(sql)

        # TODO should have a unified way to trigger refreshes
        program = scrape.program(program_code)

        if program is None:
            return None

        if res:
            return program

        sql = """
              INSERT INTO program
              VALUES ('%s', '%s', '%s', '%s', '%d', '%d')
              """ % (
            program["program_code"],
            program["title"],
            program["level"],
            program["abbreviation"],
            program["durationYears"],
            program["units"],
        )

        self._db.commit(sql)

        return program

    def add_program_course_list(self, program_code):
        """

        :param program_code: String, 4 digit code of desired program
        :return:
        """
        course_list = scrape.program_course_list(program_code)

        for course_code in tqdm(course_list):
            # if self._dev_course_count > 5:
            # return
            # self._dev_course_count += 1

            course = self.add_course(course_code)
            if course is None:
                continue

            sql = """
                  INSERT INTO program_course_list
                      (course_code, program_code)
                  SELECT '%s', '%s'
                  WHERE NOT EXISTS (
                      SELECT course_code
                      FROM program_course_list
                      WHERE course_code = '%s' AND program_code = '%s'
                  );
                  """ % (
                course_code,
                program_code,
                course_code,
                program_code,
            )

            self._db.commit(sql)

        return course_list

    def add_plan(self, plan_code, plan_title):
        """

        :param plan_code: String, 5 letter plan key followed by 4 digit
                            program code (e.g. SOFTWX2342)
        :param plan_title: String, plan title
        :return:
        """
        sql = (
            """
            SELECT plan_code
            FROM plan
            WHERE plan_code = '%s'
            """
            % plan_code
        )
        res = self._db.select(sql)

        plan = scrape.plan(plan_code, plan_title)

        if plan is None:
            return None

        if res:
            return plan

        sql = """
              INSERT INTO plan
              VALUES ('%s', '%s', '%s')
              """ % (
            plan["plan_code"],
            plan["program_code"],
            plan["title"],
        )

        self._db.commit(sql)

        return plan

    def add_plan_course_list(self, plan_code, plan_course_list):
        """

        :param plan_code: String, 5 letter plan key followed by 4 digit
                            program code (e.g. SOFTWX2342)
        :param plan_course_list: List, containing Strings, all course codes
                            (e.g. CSSE1001)
        :return: None
        """
        for course_code in tqdm(plan_course_list):
            # if self._dev_course_count > 20:
            # return
            # self._dev_course_count += 1

            course = self.add_course(course_code)
            if course is None:
                continue

            sql = """
                INSERT INTO plan_course_list
                    (course_code, plan_code)
                SELECT '%s', '%s'
                WHERE NOT EXISTS (
                    SELECT course_code
                    FROM plan_course_list
                    WHERE course_code = '%s' AND plan_code = '%s'
                );
                """ % (
                course_code,
                plan_code,
                course_code,
                plan_code,
            )

            self._db.commit(sql)

    def add_course(self, course_code):
        """

        :param course_code: String, 4 letters followed by 4 digits
                                (e.g. MATH1051)
        :return:
        """

        # Check for db entry for course. Don't scrape it if yes
        if len(course_code) != 8:
            return None
        sql = (
            """
            SELECT course_code
            FROM course
            WHERE course_code = '%s'
            """
            % course_code
        )
        res = self._db.select(sql)
        if res:
            # dont need course object for anything, so just return nothing
            return False

        course = scrape.course(course_code)

        # # add invalid course to db
        if course is None:
            sql = (
                """
              INSERT INTO course
              (course_code, invalid)
              VALUES ('%s', 'true')
              """
                % course_code
            )

            self._db.commit(sql)
            return None

        sql = """
              INSERT INTO course
              VALUES ('%s', '%s', '%s', '%s', 
              '%d', '%s', '%s', '%s', '%s', 'false')
              """ % (
            course["course_code"],
            course["title"],
            course["description"],
            course["raw_prereqs"],
            course["units"],
            course["course_profile_id"],
            course["semester_offerings"][0],
            course["semester_offerings"][1],
            course["semester_offerings"][2],
        )

        self._db.commit(sql)

        self.add_incompatible_courses(course_code, course["incompatible_courses"])

        return course

    def add_incompatible_courses(self, course_code, incompatible_courses):
        """

        :param course_code: String, course code of parent
        :param incompatible_courses: List, course code/s as Strings
        :return:
        """
        if incompatible_courses is None:
            return

        for i_course_code in incompatible_courses:
            if len(i_course_code) != 8:
                self._logfile.write(course_code + "\n")
                continue
            # Ensure all courses are added to `course` table
            self.add_course(i_course_code)

            sql = """
                SELECT course_code
                FROM incompatible_courses
                WHERE course_code = '%s'
                AND incompatible_course_code = '%s'
                """ % (
                course_code,
                i_course_code,
            )
            res = self._db.select(sql)
            if res:
                continue

            sql = """
                  INSERT INTO incompatible_courses
                  VALUES ('%s', '%s')
                  """ % (
                course_code,
                i_course_code,
            )

            self._db.commit(sql)


if __name__ == "__main__":
    pipeline = Pipeline()
    pipeline.reset()
    pipeline.run()
