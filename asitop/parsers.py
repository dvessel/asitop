def parse_thermal_pressure(powermetrics_parse):
    return powermetrics_parse["thermal_pressure"]


def parse_cpu_metrics(powermetrics_parse):
    e_core = []
    p_core = []
    cpu_metrics = powermetrics_parse["processor"]
    cpu_metric_dict = {}
    # cpu_clusters
    cpu_clusters = cpu_metrics["clusters"]
    for cluster in cpu_clusters:
        name = cluster["name"]
        cpu_metric_dict[name+"_freq_Mhz"] = int(cluster["freq_hz"]/(1e6))
        cpu_metric_dict[name+"_active"] = int((1 - cluster["idle_ratio"])*100)
        for cpu in cluster["cpus"]:
            name = 'E-Cluster' if name[0] == 'E' else 'P-Cluster'
            core = e_core if name[0] == 'E' else p_core
            core.append(cpu["cpu"])
            cpu_metric_dict[name + str(cpu["cpu"]) + "_freq_Mhz"] = int(cpu["freq_hz"] / (1e6))
            cpu_metric_dict[name + str(cpu["cpu"]) + "_active"] = int((1 - cpu["idle_ratio"]) * 100)
    cpu_metric_dict["e_core"] = e_core
    cpu_metric_dict["p_core"] = p_core
    if "E-Cluster_active" not in cpu_metric_dict:
        # M1 Ultra
        cpu_metric_dict["E-Cluster_active"] = int(
            (cpu_metric_dict["E0-Cluster_active"] + cpu_metric_dict["E1-Cluster_active"])/2)
    if "E-Cluster_freq_Mhz" not in cpu_metric_dict:
        # M1 Ultra
        cpu_metric_dict["E-Cluster_freq_Mhz"] = max(
            cpu_metric_dict["E0-Cluster_freq_Mhz"], cpu_metric_dict["E1-Cluster_freq_Mhz"])
    if "P-Cluster_active" not in cpu_metric_dict:
        if "P2-Cluster_active" in cpu_metric_dict:
            # M1 Ultra
            cpu_metric_dict["P-Cluster_active"] = int((cpu_metric_dict["P0-Cluster_active"] + cpu_metric_dict["P1-Cluster_active"] +
                                                      cpu_metric_dict["P2-Cluster_active"] + cpu_metric_dict["P3-Cluster_active"]) / 4)
        else:
            cpu_metric_dict["P-Cluster_active"] = int(
                (cpu_metric_dict["P0-Cluster_active"] + cpu_metric_dict["P1-Cluster_active"])/2)
    if "P-Cluster_freq_Mhz" not in cpu_metric_dict:
        if "P2-Cluster_freq_Mhz" in cpu_metric_dict:
            # M1 Ultra
            freqs = [
                cpu_metric_dict["P0-Cluster_freq_Mhz"],
                cpu_metric_dict["P1-Cluster_freq_Mhz"],
                cpu_metric_dict["P2-Cluster_freq_Mhz"],
                cpu_metric_dict["P3-Cluster_freq_Mhz"]]
            cpu_metric_dict["P-Cluster_freq_Mhz"] = max(freqs)
        else:
            cpu_metric_dict["P-Cluster_freq_Mhz"] = max(
                cpu_metric_dict["P0-Cluster_freq_Mhz"], cpu_metric_dict["P1-Cluster_freq_Mhz"])
    # power
    cpu_metric_dict["ane_W"] = cpu_metrics["ane_energy"]/1000
    cpu_metric_dict["cpu_W"] = cpu_metrics["cpu_energy"]/1000
    cpu_metric_dict["gpu_W"] = cpu_metrics["gpu_energy"]/1000
    cpu_metric_dict["combined_W"] = (cpu_metrics["ane_energy"] +
                                     cpu_metrics["cpu_energy"] +
                                     cpu_metrics["gpu_energy"])/1000
    return cpu_metric_dict


def parse_gpu_metrics(powermetrics_parse):
    gpu_metrics = powermetrics_parse["gpu"]
    gpu_metrics_dict = {
        "freq_MHz": int(gpu_metrics["freq_hz"]),
        "active": int((1 - gpu_metrics["idle_ratio"])*100),
    }
    return gpu_metrics_dict
