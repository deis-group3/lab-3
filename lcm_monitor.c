#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <lcm/lcm.h>

// Include the generated LCM message headers
#include "convoy_heartbeat_t.h"
#include "convoy_warning_t.h"
#include "convoy_mode_t.h"
#include "convoy_status_t.h"

// Global LCM instance for cleanup
static lcm_t *g_lcm = NULL;
static int g_running = 1;

/**
 * Convert Unix timestamp (microseconds) to human readable time
 */
void print_timestamp(int64_t timestamp_us) {
    time_t timestamp_sec = timestamp_us / 1000000;
    int microseconds = timestamp_us % 1000000;
    struct tm *tm_info = localtime(&timestamp_sec);
    char buffer[80];
    strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", tm_info);
    printf("[%s.%06d] ", buffer, microseconds);
}

/**
 * Handler for heartbeat messages
 */
void heartbeat_handler(const lcm_recv_buf_t *rbuf, const char *channel,
                      const convoy_heartbeat_t *msg, void *userdata) {
    (void)rbuf; (void)channel; (void)userdata; // Suppress unused parameter warnings
    print_timestamp(msg->timestamp);
    printf("HEARTBEAT from vehicle %d\n", msg->vehicle_id);
}

/**
 * Handler for warning messages
 */
void warning_handler(const lcm_recv_buf_t *rbuf, const char *channel,
                    const convoy_warning_t *msg, void *userdata) {
    (void)rbuf; (void)channel; (void)userdata; // Suppress unused parameter warnings
    print_timestamp(msg->timestamp);
    printf("WARNING from vehicle %d: danger=%s", 
           msg->vehicle_id, 
           msg->danger_detected ? "TRUE" : "FALSE");
    
    if (msg->description && strlen(msg->description) > 0) {
        printf(", description='%s'", msg->description);
    }
    printf("\n");
}

/**
 * Handler for mode change messages
 */
void mode_handler(const lcm_recv_buf_t *rbuf, const char *channel,
                 const convoy_mode_t *msg, void *userdata) {
    (void)rbuf; (void)channel; (void)userdata; // Suppress unused parameter warnings
    const char* mode_names[] = {"Single Vehicle", "Head in Convoy", "In Convoy"};
    
    print_timestamp(msg->timestamp);
    printf("MODE CHANGE from vehicle %d: mode=%d (%s)", 
           msg->vehicle_id, 
           msg->mode,
           (msg->mode >= 0 &&  msg->mode <= 2) ? mode_names[msg->mode] : "Unknown");
    
    if (msg->mode_description && strlen(msg->mode_description) > 0) {
        printf(", description='%s'", msg->mode_description);
    }
    printf("\n");
}

/**
 * Handler for status messages
 */
void status_handler(const lcm_recv_buf_t *rbuf, const char *channel,
                   const convoy_status_t *msg, void *userdata) {
    (void)rbuf; (void)channel; (void)userdata; // Suppress unused parameter warnings
    const char* mode_names[] = {"Single Vehicle", "Head in Convoy", "In Convoy"};
    
    print_timestamp(msg->timestamp);
    printf("STATUS from vehicle %d:\n", msg->vehicle_id);
    printf("  - Driving Mode: %d (%s)\n", 
           msg->driving_mode,
           (msg->driving_mode >= 0 && msg->driving_mode <= 2) ? mode_names[msg->driving_mode] : "Unknown");
    printf("  - Motion Detected: %s\n", msg->motion_detected ? "YES" : "NO");
    printf("  - Brake Lights: %s\n", msg->brake_lights_on ? "ON" : "OFF");
    printf("  - System Running: %s\n", msg->system_running ? "YES" : "NO");
    
    if (msg->status_message && strlen(msg->status_message) > 0) {
        printf("  - Message: %s\n", msg->status_message);
    }
    printf("\n");
}

/**
 * Signal handler for clean shutdown
 */
void signal_handler(int sig) {
    printf("\nReceived signal %d, shutting down...\n", sig);
    g_running = 0;
}

/**
 * Print usage information
 */
void print_usage(const char *program_name) {
    printf("Usage: %s [options]\n", program_name);
    printf("Options:\n");
    printf("  -h, --help     Show this help message\n");
    printf("  -c <channel>   Subscribe to specific channel (default: all)\n");
    printf("\nChannels:\n");
    printf("  HEARTBEAT      Vehicle heartbeat messages\n");
    printf("  WARNING        Danger/obstacle warning messages\n");
    printf("  MODE           Driving mode change messages\n");
    printf("  STATUS         Vehicle status messages\n");
    printf("\nPress Ctrl+C to stop\n");
}

int main(int argc, char *argv[]) {
    const char *specific_channel = NULL;
    
    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else if (strcmp(argv[i], "-c") == 0 && i + 1 < argc) {
            specific_channel = argv[++i];
        }
    }
    
    // Initialize LCM with UDP TTL=0 for localhost only
    g_lcm = lcm_create("udpm://239.255.76.67:7667?ttl=0");
    if (!g_lcm) {
        fprintf(stderr, "Error: Failed to initialize LCM\n");
        return 1;
    }
    
    // Set up signal handlers for graceful shutdown
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    printf("LCM Message Monitor Started\n");
    printf("========================\n");
    
    // Subscribe to channels
    if (specific_channel) {
        printf("Subscribing to channel: %s\n", specific_channel);
        if (strcmp(specific_channel, "HEARTBEAT") == 0) {
            convoy_heartbeat_t_subscribe(g_lcm, "HEARTBEAT", heartbeat_handler, NULL);
        } else if (strcmp(specific_channel, "WARNING") == 0) {
            convoy_warning_t_subscribe(g_lcm, "WARNING", warning_handler, NULL);
        } else if (strcmp(specific_channel, "MODE") == 0) {
            convoy_mode_t_subscribe(g_lcm, "MODE", mode_handler, NULL);
        } else if (strcmp(specific_channel, "STATUS") == 0) {
            convoy_status_t_subscribe(g_lcm, "STATUS", status_handler, NULL);
        } else {
            fprintf(stderr, "Warning: Unknown channel '%s'\n", specific_channel);
        }
    } else {
        printf("Subscribing to all convoy channels...\n");
        convoy_heartbeat_t_subscribe(g_lcm, "HEARTBEAT", heartbeat_handler, NULL);
        convoy_warning_t_subscribe(g_lcm, "WARNING", warning_handler, NULL);
        convoy_mode_t_subscribe(g_lcm, "MODE", mode_handler, NULL);
        convoy_status_t_subscribe(g_lcm, "STATUS", status_handler, NULL);
    }
    
    printf("Waiting for messages... (Press Ctrl+C to stop)\n\n");
    
    // Main message loop
    while (g_running) {
        // Handle LCM messages with timeout
        int status = lcm_handle_timeout(g_lcm, 100); // 100ms timeout
        
        if (status < 0) {
            fprintf(stderr, "Error: LCM handle failed\n");
            break;
        }
        // status == 0 means timeout (no messages), which is normal
    }
    
    // Cleanup
    printf("Cleaning up...\n");
    if (g_lcm) {
        lcm_destroy(g_lcm);
    }
    
    printf("LCM Message Monitor stopped.\n");
    return 0;
}