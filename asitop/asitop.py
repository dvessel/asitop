import time
import argparse
from collections import deque
from dashing import VSplit, HSplit, HGauge, HChart, VGauge
from .utils import (build_enqueue_thread,
                    clear_console,
                    get_ram_metrics_dict,
                    get_soc_info,
                    parse_powermetrics,
                    run_powermetrics_process)

parser = argparse.ArgumentParser(
    description='asitop: Performance monitoring CLI tool for Apple Silicon')
parser.add_argument('--interval', type=int, default=1,
                    help='Display interval and sampling interval for powermetrics (seconds)')
parser.add_argument('--color', type=int, default=2,
                    help='Choose display color (0~8)')
parser.add_argument('--avg', type=int, default=30,
                    help='Interval for averaged values (seconds)')
parser.add_argument('--show_cores', type=bool, default=False,
                    help='Choose show cores mode')
args = parser.parse_args()


def main():
    print("\nASITOP - Performance monitoring CLI tool for Apple Silicon")
    print("You can update ASITOP by running `pip install asitop --upgrade`")
    print("Get help at `https://github.com/tlkh/asitop`")
    print("P.S. You are recommended to run ASITOP with `sudo asitop`\n")
    print("\n[1/3] Loading ASITOP\n")
    print("\033[?25l")

    cpu1_gauge = HGauge(title="E-CPU Usage", val=0, color=args.color)
    cpu2_gauge = HGauge(title="P-CPU Usage", val=0, color=args.color)
    gpu_gauge = HGauge(title="GPU Usage", val=0, color=args.color)
    ane_gauge = HGauge(title="ANE", val=0, color=args.color)
    gpu_ane_gauges = [gpu_gauge, ane_gauge]

    soc_info_dict = get_soc_info()
    e_core_count = soc_info_dict["e_core_count"]
    e_core_gauges = [VGauge(val=0, color=args.color, border_color=args.color) for _ in range(e_core_count)]
    p_core_count = soc_info_dict["p_core_count"]
    p_core_gauges = [VGauge(val=0, color=args.color, border_color=args.color) for _ in range(min(p_core_count, 8))]
    p_core_split = [HSplit(
        *p_core_gauges,
    )]
    if p_core_count > 8:
        p_core_gauges_ext = [VGauge(val=0, color=args.color, border_color=args.color) for _ in range(p_core_count - 8)]
        p_core_split.append(HSplit(
            *p_core_gauges_ext,
        ))
    processor_gauges = [cpu1_gauge,
                        HSplit(*e_core_gauges),
                        cpu2_gauge,
                        *p_core_split,
                        *gpu_ane_gauges
                        ] if args.show_cores else [
        HSplit(cpu1_gauge, cpu2_gauge),
        HSplit(*gpu_ane_gauges)
    ]
    processor_split = VSplit(
        *processor_gauges,
        title="Processor Utilization",
        border_color=args.color,
    )

    ram_gauge = HGauge(title="RAM Usage", val=0, color=args.color)
    memory_gauges = VSplit(
        ram_gauge,
        border_color=args.color,
        title="Memory"
    )

    cpu_power_chart = HChart(title="CPU Power", color=args.color)
    gpu_power_chart = HChart(title="GPU Power", color=args.color)
    power_charts = VSplit(
        cpu_power_chart,
        gpu_power_chart,
        title="Power Chart",
        border_color=args.color,
    ) if args.show_cores else HSplit(
        cpu_power_chart,
        gpu_power_chart,
        title="Power Chart",
        border_color=args.color,
    )

    ui = HSplit(
        processor_split,
        VSplit(
            memory_gauges,
            power_charts,
        )
    ) if args.show_cores else VSplit(
        processor_split,
        memory_gauges,
        power_charts,
    )

    usage_gauges = ui.items[0]

    cpu_title = "".join([
        soc_info_dict["name"],
        " (cores: ",
        str(soc_info_dict["e_core_count"]),
        "E+",
        str(soc_info_dict["p_core_count"]),
        "P+",
        str(soc_info_dict["gpu_core_count"]),
        "GPU)"
    ])
    usage_gauges.title = cpu_title
    cpu_max_power = soc_info_dict["cpu_max_power"]
    gpu_max_power = soc_info_dict["gpu_max_power"]
    ane_max_power = 8.0

    cpu_peak_power = 0
    gpu_peak_power = 0
    combined_peak_power = 0

    print("\n[2/3] Starting powermetrics process\n")

    powermetrics_process = run_powermetrics_process(interval=args.interval * 1000)
    queue, _thread = build_enqueue_thread(powermetrics_process.stdout)

    print("\n[3/3] Waiting for first reading...\n")

    def get_reading(wait=0.1):
        ready = parse_powermetrics(queue)
        while not ready:
            time.sleep(wait)
            ready = parse_powermetrics(queue)
        return ready

    ready = get_reading()
    last_timestamp = ready[-1]

    def get_avg(inlist):
        avg = sum(inlist) / len(inlist)
        return avg

    avg_combined_power_list = deque([], maxlen=int(args.avg / args.interval))
    avg_cpu_power_list = deque([], maxlen=int(args.avg / args.interval))
    avg_gpu_power_list = deque([], maxlen=int(args.avg / args.interval))

    clear_console()

    try:
        while True:
            ready = parse_powermetrics(queue)
            if ready:
                cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, timestamp = ready

                if timestamp > last_timestamp:
                    last_timestamp = timestamp

                    if thermal_pressure == "Nominal":
                        thermal_throttle = "no"
                    else:
                        thermal_throttle = "yes"

                    cpu1_gauge.title = "".join([
                        "E-CPU Usage: ",
                        str(cpu_metrics_dict["E-Cluster_active"]),
                        "% @ ",
                        str(cpu_metrics_dict["E-Cluster_freq_Mhz"]),
                        " MHz"
                    ])
                    cpu1_gauge.value = cpu_metrics_dict["E-Cluster_active"]

                    cpu2_gauge.title = "".join([
                        "P-CPU Usage: ",
                        str(cpu_metrics_dict["P-Cluster_active"]),
                        "% @ ",
                        str(cpu_metrics_dict["P-Cluster_freq_Mhz"]),
                        " MHz"
                    ])
                    cpu2_gauge.value = cpu_metrics_dict["P-Cluster_active"]

                    if args.show_cores:
                        core_count = 0
                        for i in cpu_metrics_dict["e_core"]:
                            e_core_gauges[core_count % 4].title = "".join([
                                "Core-" + str(i + 1) + " ",
                                str(cpu_metrics_dict["E-Cluster" + str(i) + "_active"]),
                                "%",
                            ])
                            e_core_gauges[core_count % 4].value = cpu_metrics_dict["E-Cluster" + str(i) + "_active"]
                            core_count += 1
                        core_count = 0
                        for i in cpu_metrics_dict["p_core"]:
                            core_gauges = p_core_gauges if core_count < 8 else p_core_gauges_ext
                            core_gauges[core_count % 8].title = "".join([
                                ("Core-" if p_core_count < 6 else 'C-') + str(i + 1) + " ",
                                str(cpu_metrics_dict["P-Cluster" + str(i) + "_active"]),
                                "%",
                            ])
                            core_gauges[core_count % 8].value = cpu_metrics_dict["P-Cluster" + str(i) + "_active"]
                            core_count += 1

                    gpu_gauge.title = "".join([
                        "GPU Usage: ",
                        str(gpu_metrics_dict["active"]),
                        "% @ ",
                        str(gpu_metrics_dict["freq_MHz"]),
                        " MHz"
                    ])
                    gpu_gauge.value = gpu_metrics_dict["active"]

                    ane_util_percent = int(
                        cpu_metrics_dict["ane_W"] / args.interval / ane_max_power * 100)
                    ane_gauge.title = "".join([
                        "ANE Usage: ",
                        str(ane_util_percent),
                        "% @ ",
                        '{0:.1f}'.format(
                            cpu_metrics_dict["ane_W"] / args.interval),
                        " W"
                    ])
                    ane_gauge.value = ane_util_percent

                    ram_metrics_dict = get_ram_metrics_dict()

                    if ram_metrics_dict["swap_total_GB"] < 0.1:
                        ram_gauge.title = "".join([
                            "RAM Usage: ",
                            str(ram_metrics_dict["used_GB"]),
                            "/",
                            str(ram_metrics_dict["total_GB"]),
                            "GB - swap inactive"
                        ])
                    else:
                        ram_gauge.title = "".join([
                            "RAM Usage: ",
                            str(ram_metrics_dict["used_GB"]),
                            "/",
                            str(ram_metrics_dict["total_GB"]),
                            "GB",
                            " - swap:",
                            str(ram_metrics_dict["swap_used_GB"]),
                            "/",
                            str(ram_metrics_dict["swap_total_GB"]),
                            "GB"
                        ])
                    ram_gauge.value = ram_metrics_dict["free_percent"]

                    combined_power_W = cpu_metrics_dict["combined_W"] / \
                                      args.interval
                    if combined_power_W > combined_peak_power:
                        combined_peak_power = combined_power_W
                    avg_combined_power_list.append(combined_power_W)
                    avg_combined_power = get_avg(avg_combined_power_list)
                    power_charts.title = "".join([
                        "Combined Power: ",
                        '{0:.2f}'.format(combined_power_W),
                        "W (avg: ",
                        '{0:.2f}'.format(avg_combined_power),
                        "W peak: ",
                        '{0:.2f}'.format(combined_peak_power),
                        "W) throttle: ",
                        thermal_throttle,
                    ])

                    cpu_power_percent = int(
                        cpu_metrics_dict["cpu_W"] / args.interval / cpu_max_power * 100)
                    cpu_power_W = cpu_metrics_dict["cpu_W"] / args.interval
                    if cpu_power_W > cpu_peak_power:
                        cpu_peak_power = cpu_power_W
                    avg_cpu_power_list.append(cpu_power_W)
                    avg_cpu_power = get_avg(avg_cpu_power_list)
                    cpu_power_chart.title = "".join([
                        "CPU: ",
                        '{0:.2f}'.format(cpu_power_W),
                        "W (avg: ",
                        '{0:.2f}'.format(avg_cpu_power),
                        "W peak: ",
                        '{0:.2f}'.format(cpu_peak_power),
                        "W)"
                    ])
                    cpu_power_chart.append(cpu_power_percent)

                    gpu_power_percent = int(
                        cpu_metrics_dict["gpu_W"] / args.interval / gpu_max_power * 100)
                    gpu_power_W = cpu_metrics_dict["gpu_W"] / args.interval
                    if gpu_power_W > gpu_peak_power:
                        gpu_peak_power = gpu_power_W
                    avg_gpu_power_list.append(gpu_power_W)
                    avg_gpu_power = get_avg(avg_gpu_power_list)
                    gpu_power_chart.title = "".join([
                        "GPU: ",
                        '{0:.2f}'.format(gpu_power_W),
                        "W (avg: ",
                        '{0:.2f}'.format(avg_gpu_power),
                        "W peak: ",
                        '{0:.2f}'.format(gpu_peak_power),
                        "W)"
                    ])
                    gpu_power_chart.append(gpu_power_percent)

                    ui.display()


    except KeyboardInterrupt:
        print("Stopping...")
        print("\033[?25h")

    return powermetrics_process


if __name__ == "__main__":
    powermetrics_process = main()
    try:
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
    except Exception as e:
        print(e)
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
