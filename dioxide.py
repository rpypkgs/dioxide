import sys

def main(argv):
    return 0

def target(driver, *args):
    driver.exe_name = "dioxide"
    return main, None

if __name__ == "__main__":
    sys.exit(main(sys.argv))
