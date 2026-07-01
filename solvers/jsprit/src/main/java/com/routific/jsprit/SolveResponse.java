package com.routific.jsprit;

import java.util.List;

/** POST /solve response body. */
public class SolveResponse {

    public List<Route> routes;

    /** IDs of services that could not be assigned to any vehicle */
    public List<String> unserved_ids;

    public static class Route {
        public String vehicle_id;

        /**
         * Time (seconds from midnight) at which the vehicle departs its start depot.
         * Corresponds to route.getStart().getEndTime() in jsprit.
         */
        public double start_time;

        /** Service IDs in the order the vehicle will visit them */
        public List<String> service_ids;

        public Route(String vehicleId, double startTime, List<String> serviceIds) {
            this.vehicle_id = vehicleId;
            this.start_time = startTime;
            this.service_ids = serviceIds;
        }
    }
}
