package com.routific.jsprit;

import java.util.List;

/**
 * POST /solve request body.
 *
 * Locations are referenced by integer index into the travel_times matrix.
 * The matrix contains travel times in seconds (doubles).
 */
public class SolveRequest {

    public List<Vehicle> vehicles;
    public List<Service> services;

    /** travel_times[from][to] — seconds between location indices */
    public double[][] travel_times;

    /** Maximum wall-clock time to spend solving, in milliseconds. null = jsprit default (2000 iterations). */
    public Long time_limit_ms;

    /** When true, a fixed cost of maxCost*20 is applied per vehicle to push jsprit toward fewer vehicles. */
    public boolean minimize_vehicles;

    public static class Vehicle {
        public String id;
        public int start_index;

        /** null = open route (vehicle does not return to depot) */
        public Integer end_index;

        /** 0 or negative = unlimited capacity */
        public double capacity;

        /** seconds from midnight */
        public double earliest_start;

        /** null = no shift-end constraint */
        public Double latest_end;
    }

    public static class Service {
        public String id;
        public int location_index;

        /** service duration in seconds */
        public double duration;

        /** capacity units consumed; 0 = no capacity demand */
        public double demand;

        /** null = no time window constraint */
        public TimeWindow time_window;
    }

    public static class TimeWindow {
        /** earliest time service may start, seconds from midnight */
        public double earliest;

        /** latest time service may start, seconds from midnight */
        public double latest;
    }
}
