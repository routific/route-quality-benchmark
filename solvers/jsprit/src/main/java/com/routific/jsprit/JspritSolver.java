package com.routific.jsprit;

import com.graphhopper.jsprit.core.algorithm.VehicleRoutingAlgorithm;
import com.graphhopper.jsprit.core.algorithm.box.Jsprit;
import com.graphhopper.jsprit.core.algorithm.termination.TimeTermination;
import com.graphhopper.jsprit.core.problem.Location;
import com.graphhopper.jsprit.core.problem.VehicleRoutingProblem;
import com.graphhopper.jsprit.core.util.VehicleRoutingTransportCostsMatrix;
import com.graphhopper.jsprit.core.problem.job.Service;
import com.graphhopper.jsprit.core.problem.solution.VehicleRoutingProblemSolution;
import com.graphhopper.jsprit.core.problem.solution.route.VehicleRoute;
import com.graphhopper.jsprit.core.problem.solution.route.activity.TourActivity;
import com.graphhopper.jsprit.core.problem.vehicle.VehicleImpl;
import com.graphhopper.jsprit.core.problem.vehicle.VehicleTypeImpl;
import com.graphhopper.jsprit.core.util.Solutions;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.stream.Collectors;

public class JspritSolver {

    public static SolveResponse solve(SolveRequest req) {
        VehicleRoutingProblem.Builder vrpBuilder = VehicleRoutingProblem.Builder.newInstance()
                .setFleetSize(VehicleRoutingProblem.FleetSize.FINITE);

        // Travel time matrix (asymmetric — Routific matrices are not always symmetric)
        VehicleRoutingTransportCostsMatrix.Builder costBuilder =
                VehicleRoutingTransportCostsMatrix.Builder.newInstance(false);
        int n = req.travel_times.length;
        double maxCost = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                // Location.Builder.setIndex(i) defaults the string ID to String.valueOf(i)
                costBuilder.addTransportTime(String.valueOf(i), String.valueOf(j), req.travel_times[i][j]);
                costBuilder.addTransportDistance(String.valueOf(i), String.valueOf(j), req.travel_times[i][j]);
                if (req.travel_times[i][j] > maxCost) maxCost = req.travel_times[i][j];
            }
        }
        vrpBuilder.setRoutingCost(costBuilder.build());

        // Vehicles
        for (SolveRequest.Vehicle v : req.vehicles) {
            // 0 / negative capacity → unlimited; cap at MAX_VALUE to avoid int overflow
            int capacity = v.capacity <= 0
                    ? Integer.MAX_VALUE
                    : (int) Math.min(v.capacity, Integer.MAX_VALUE);

            VehicleTypeImpl.Builder typeBuilder = VehicleTypeImpl.Builder.newInstance("type_" + v.id)
                    .addCapacityDimension(0, capacity);
            if (req.minimize_vehicles) {
                typeBuilder.setFixedCost(maxCost * 20);
            }
            VehicleTypeImpl type = typeBuilder.build();

            VehicleImpl.Builder vb = VehicleImpl.Builder.newInstance(v.id)
                    .setStartLocation(Location.Builder.newInstance().setIndex(v.start_index).build())
                    .setEarliestStart(v.earliest_start)
                    .setType(type);

            if (v.end_index != null) {
                vb.setEndLocation(Location.Builder.newInstance().setIndex(v.end_index).build());
            } else {
                vb.setReturnToDepot(false);
            }
            if (v.latest_end != null) {
                vb.setLatestArrival(v.latest_end);
            }
            vrpBuilder.addVehicle(vb.build());
        }

        // Services
        for (SolveRequest.Service s : req.services) {
            int demand = (int) Math.max(0, Math.min(s.demand, Integer.MAX_VALUE));

            Service.Builder sb = Service.Builder.newInstance(s.id)
                    .setLocation(Location.Builder.newInstance().setIndex(s.location_index).build())
                    .setServiceTime(s.duration)
                    .addSizeDimension(0, demand);

            if (s.time_window != null) {
                sb.addTimeWindow(s.time_window.earliest, s.time_window.latest);
            }
            vrpBuilder.addJob(sb.build());
        }

        VehicleRoutingProblem vrp = vrpBuilder.build();
        VehicleRoutingAlgorithm algorithm = Jsprit.createAlgorithm(vrp);
        if (req.time_limit_ms != null) {
            algorithm.addTerminationCriterion(new TimeTermination(req.time_limit_ms));
        }

        Collection<VehicleRoutingProblemSolution> solutions = algorithm.searchSolutions();
        VehicleRoutingProblemSolution best = Solutions.bestOf(solutions);

        // Build routes — skip empty routes (vehicles with no assigned visits)
        List<SolveResponse.Route> routes = new ArrayList<>();
        for (VehicleRoute route : best.getRoutes()) {
            List<String> serviceIds = route.getActivities().stream()
                    .filter(a -> a instanceof TourActivity.JobActivity)
                    .map(a -> ((TourActivity.JobActivity) a).getJob().getId())
                    .collect(Collectors.toList());
            if (serviceIds.isEmpty()) {
                continue;
            }
            routes.add(new SolveResponse.Route(
                    route.getVehicle().getId(),
                    route.getStart().getEndTime(),
                    serviceIds));
        }

        List<String> unservedIds = best.getUnassignedJobs().stream()
                .map(job -> job.getId())
                .collect(Collectors.toList());

        SolveResponse response = new SolveResponse();
        response.routes = routes;
        response.unserved_ids = unservedIds;
        return response;
    }
}
