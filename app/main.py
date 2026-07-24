"""Application entrypoint."""


def main() -> None:
    print("Female Character Network Visualizer scaffold")
    print("Start local UI with: python3 -m streamlit run app/ui/app.py")
    print("UI launches Docker container for pipeline runs")
    print(
        "PROGRESS\tstage=startup\tcompleted=0\ttotal=0\t"
        "status=running\tmessage=Container started"
    )
    print(
        "PROGRESS\tstage=scaffold\tcompleted=0\ttotal=0\t"
        "status=completed\tmessage=Scaffold run completed"
    )


if __name__ == "__main__":
    main()
