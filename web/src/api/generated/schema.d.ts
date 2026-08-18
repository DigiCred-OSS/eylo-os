export interface paths {
    "/api/{organization_id}/agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Agents */
        get: operations["list_agents_api__organization_id__agents_get"];
        put?: never;
        /**
         * Create Agent
         * @description Create a new agent for the current user's organization.
         */
        post: operations["create_agent_api__organization_id__agents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Agent
         * @description Retrieve details of a specific agent.
         */
        get: operations["get_agent_api__organization_id__agents__agent_id__get"];
        /**
         * Update Agent
         * @description Create a new agent for the current user's organization.
         */
        put: operations["update_agent_api__organization_id__agents__agent_id__put"];
        post?: never;
        /**
         * Deactivate Agent Route
         * @description Deactivate (soft delete) an agent.
         *
         *     Args:
         *         agent_id: The ID of the agent to deactivate.
         *         current_user: The authenticated user.
         *
         *     Returns:
         *         AgentResponseSchema: The deactivated agent.
         */
        delete: operations["deactivate_agent_route_api__organization_id__agents__agent_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Agent Route
         * @description Update an existing agent.
         *
         *     Args:
         *         agent_id: The ID of the agent to update.
         *         request: The request payload with update data.
         *         current_user: The authenticated user.
         *
         *     Returns:
         *         AgentResponseSchema: The updated agent.
         */
        patch: operations["update_agent_route_api__organization_id__agents__agent_id__patch"];
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/effective-voice-stack": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Effective Voice Stack
         * @description Return the exact voice refs copied into the published Agent revision.
         */
        get: operations["get_effective_voice_stack_api__organization_id__agents__agent_id__effective_voice_stack_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Agent Tools
         * @description List all tools assigned to an agent.
         */
        get: operations["list_agent_tools_api__organization_id__agents__agent_id__tools_get"];
        put?: never;
        /**
         * Assign Tool To Agent
         * @description Assign a tool to an agent.
         */
        post: operations["assign_tool_to_agent_api__organization_id__agents__agent_id__tools_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/tools/{tool_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Remove Tool From Agent
         * @description Remove a tool from an agent.
         */
        delete: operations["remove_tool_from_agent_api__organization_id__agents__agent_id__tools__tool_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Publish Agent
         * @description Publish the complete mutable draft as one immutable revision.
         */
        put: operations["publish_agent_api__organization_id__agents__agent_id__publish_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/unpublish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Withdraw Agent
         * @description Withdraw the stable alias; already pinned work keeps its exact revision.
         */
        put: operations["withdraw_agent_api__organization_id__agents__agent_id__unpublish_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/revisions/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Revoke Agent Revision
         * @description Emergency-revoke one exact revision and request run cancellation.
         */
        post: operations["revoke_agent_revision_api__organization_id__agents__agent_id__revisions_revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-runs/budget": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Budget */
        get: operations["get_budget_api__organization_id__agent_runs_budget_get"];
        /** Put Budget */
        put: operations["put_budget_api__organization_id__agent_runs_budget_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List All */
        get: operations["list_all_api__organization_id__agent_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-runs/{run_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel */
        post: operations["cancel_api__organization_id__agent_runs__run_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-runs/{run_id}/input-requests/{request_id}/response": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Answer */
        post: operations["answer_api__organization_id__agent_runs__run_id__input_requests__request_id__response_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read One */
        get: operations["read_one_api__organization_id__agent_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/background-agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Background Agents
         * @description List every background agent attached to this agent, enabled or not.
         */
        get: operations["list_background_agents_api__organization_id__agents__agent_id__background_agents_get"];
        put?: never;
        /**
         * Attach Background Agent
         * @description Attach a background agent. Always created disabled.
         *
         *     `enabled` on the request body is ignored: attaching and switching on are
         *     separate decisions, and the second one goes through PATCH.
         */
        post: operations["attach_background_agent_api__organization_id__agents__agent_id__background_agents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/background-agents/{background_agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Detach Background Agent
         * @description Remove an attachment. The background agent itself is untouched.
         */
        delete: operations["detach_background_agent_api__organization_id__agents__agent_id__background_agents__background_agent_id__delete"];
        options?: never;
        head?: never;
        /**
         * Set Background Agent Enabled
         * @description Enable or disable an existing attachment.
         */
        patch: operations["set_background_agent_enabled_api__organization_id__agents__agent_id__background_agents__background_agent_id__patch"];
        trace?: never;
    };
    "/api/{organization_id}/mcp-servers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Mcp Servers
         * @description Servers registered for this organization, with header values masked.
         */
        get: operations["list_mcp_servers_api__organization_id__mcp_servers_get"];
        put?: never;
        /**
         * Register Mcp Server
         * @description Record a server. Does not contact it — see the discover endpoint.
         */
        post: operations["register_mcp_server_api__organization_id__mcp_servers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/mcp-servers/{server_id}/discover": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Discover Mcp Tools
         * @description Ask the server what it offers and synchronize immutable tool revisions.
         *
         *     A changed tool appends a revision. A missing tool is withdrawn from new
         *     grants without deleting exact historical references. The response is what
         *     an operator reviews before attaching any of it to an agent; descriptions
         *     are written by the server, not by this platform.
         */
        post: operations["discover_mcp_tools_api__organization_id__mcp_servers__server_id__discover_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/mcp-servers/{server_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Mcp Server
         * @description Patch endpoint metadata or encrypted header secrets, then rediscover.
         */
        patch: operations["update_mcp_server_api__organization_id__mcp_servers__server_id__patch"];
        trace?: never;
    };
    "/api/{organization_id}/mcp-servers/{server_id}/withdraw": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Withdraw Mcp Server
         * @description Stop offering this server's tools for new Agent revisions.
         */
        post: operations["withdraw_mcp_server_api__organization_id__mcp_servers__server_id__withdraw_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/mcp-servers/{server_id}/revisions/{revision}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Revoke Mcp Server Revision
         * @description Emergency-stop an exact server revision.
         */
        post: operations["revoke_mcp_server_revision_api__organization_id__mcp_servers__server_id__revisions__revision__revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/embedding-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Embedding Configs */
        get: operations["list_embedding_configs_api_embedding_configs_get"];
        put?: never;
        /** Create Embedding Config */
        post: operations["create_embedding_config_api_embedding_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/embedding-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Embedding Config */
        get: operations["get_embedding_config_api_embedding_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Embedding Config */
        delete: operations["delete_embedding_config_api_embedding_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Embedding Config */
        patch: operations["update_embedding_config_api_embedding_configs__config_id__patch"];
        trace?: never;
    };
    "/api/embedding-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Embedding Config */
        post: operations["verify_embedding_config_api_embedding_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reranking-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Reranking Configs */
        get: operations["list_reranking_configs_api_reranking_configs_get"];
        put?: never;
        /** Create Reranking Config */
        post: operations["create_reranking_config_api_reranking_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reranking-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Reranking Config */
        get: operations["get_reranking_config_api_reranking_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Reranking Config */
        delete: operations["delete_reranking_config_api_reranking_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Reranking Config */
        patch: operations["update_reranking_config_api_reranking_configs__config_id__patch"];
        trace?: never;
    };
    "/api/reranking-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Reranking Config */
        post: operations["verify_reranking_config_api_reranking_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sandbox-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sandbox Configs */
        get: operations["list_sandbox_configs_api_sandbox_configs_get"];
        put?: never;
        /** Create Sandbox Config */
        post: operations["create_sandbox_config_api_sandbox_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sandbox-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Sandbox Config */
        get: operations["get_sandbox_config_api_sandbox_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Sandbox Config */
        delete: operations["delete_sandbox_config_api_sandbox_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Sandbox Config */
        patch: operations["update_sandbox_config_api_sandbox_configs__config_id__patch"];
        trace?: never;
    };
    "/api/sandbox-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Sandbox Config */
        post: operations["verify_sandbox_config_api_sandbox_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/objectives": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Objectives
         * @description Objectives for this organization, newest first.
         */
        get: operations["list_objectives_api__organization_id__objectives_get"];
        put?: never;
        /**
         * Create Objective
         * @description Start long-running work; the agent decides whether it needs a sandbox.
         */
        post: operations["create_objective_api__organization_id__objectives_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/objectives/{objective_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Objective
         * @description One objective, including the trail of what it has done.
         *
         *     The progress list is the thing to read when an objective misbehaves: it is
         *     what the agent itself reads on resume, so it is exactly what the agent
         *     believed had happened.
         */
        get: operations["read_objective_api__organization_id__objectives__objective_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/objectives/{objective_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Objective
         * @description Stop an objective.
         *
         *     A running objective may still finish the step it is on — cancelling stops
         *     the work, not the command already executing. Its workspace is reaped on
         *     expiry, or immediately through the sandbox route below.
         */
        post: operations["cancel_objective_api__organization_id__objectives__objective_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/sandboxes/grants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Sandbox Grants
         * @description Which agents in this organization may run code, and with what reach.
         */
        get: operations["list_sandbox_grants_api__organization_id__sandboxes_grants_get"];
        put?: never;
        /**
         * Grant Sandbox
         * @description Let an agent run code.
         *
         *     Configuring a sandbox for an organization does not grant it to every agent.
         *     The request explicitly selects both its ready config and no-egress access.
         */
        post: operations["grant_sandbox_api__organization_id__sandboxes_grants_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/sandboxes/grants/{agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Revoke Sandbox
         * @description Stop an agent running code.
         *
         *     An action already executing may finish. Every later acquisition, including
         *     restoration of a durable workspace checkpoint, requires the current grant.
         *     Revocation does not cancel the AgentRun; the session route remains the
         *     immediate kill switch for live compute.
         */
        delete: operations["revoke_sandbox_api__organization_id__sandboxes_grants__agent_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/sandboxes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Sandboxes
         * @description Workspaces this organization is holding.
         *
         *     What an operator checks when they want to know what is running and what it
         *     is costing.
         */
        get: operations["list_sandboxes_api__organization_id__sandboxes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/sandboxes/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Sandbox */
        get: operations["read_sandbox_api__organization_id__sandboxes__session_id__get"];
        put?: never;
        post?: never;
        /**
         * Destroy Sandbox
         * @description Destroy a workspace now. **The kill switch.**
         *
         *     This matters more than the usual delete endpoint: a sandbox is running
         *     code, and an operator who sees one misbehaving needs to stop it without
         *     shell access to the host and without waiting for an expiry they set in
         *     calmer circumstances.
         *
         *     Destroys rather than snapshots. An operator reaching for this wants the
         *     thing gone, not paused with its files intact.
         */
        delete: operations["destroy_sandbox_api__organization_id__sandboxes__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/memory-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Memory Configs */
        get: operations["list_memory_configs_api_memory_configs_get"];
        put?: never;
        /** Create Memory Config */
        post: operations["create_memory_config_api_memory_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/memory-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Memory Config */
        get: operations["get_memory_config_api_memory_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Memory Config */
        delete: operations["delete_memory_config_api_memory_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Memory Config */
        patch: operations["update_memory_config_api_memory_configs__config_id__patch"];
        trace?: never;
    };
    "/api/memory-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Memory Config */
        post: operations["verify_memory_config_api_memory_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/memory-configs/{config_id}/reindex": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Memory Reindex Status */
        get: operations["get_memory_reindex_status_api_memory_configs__config_id__reindex_get"];
        put?: never;
        /** Reindex Memory Config */
        post: operations["reindex_memory_config_api_memory_configs__config_id__reindex_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/memories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Memories
         * @description List saved, recalled, and expired facts for one organization.
         */
        get: operations["list_memories_api__organization_id__memories_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/memories/{memory_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Memory
         * @description Return one exact organization-owned fact and its lifecycle history.
         */
        get: operations["get_memory_api__organization_id__memories__memory_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/schedules/actions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Actions
         * @description Every action a schedule can name.
         *
         *     Exposed because the alternative is an operator guessing, and a guess
         *     becomes a schedule that fails its first run.
         */
        get: operations["list_actions_api__organization_id__schedules_actions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/schedules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List All */
        get: operations["list_all_api__organization_id__schedules_get"];
        put?: never;
        /**
         * Create
         * @description Define a schedule. Refuses anything that could not run.
         */
        post: operations["create_api__organization_id__schedules_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/schedules/{schedule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read One */
        get: operations["read_one_api__organization_id__schedules__schedule_id__get"];
        /**
         * Update
         * @description Append one explicit immutable definition revision.
         */
        put: operations["update_api__organization_id__schedules__schedule_id__put"];
        post?: never;
        /**
         * Cancel
         * @description Retire a schedule. Runs it already produced keep their history.
         */
        delete: operations["cancel_api__organization_id__schedules__schedule_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/schedules/{schedule_id}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Runs
         * @description What this schedule has actually done, newest first.
         */
        get: operations["read_runs_api__organization_id__schedules__schedule_id__runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/schedules/{schedule_id}/revisions/{revision}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Revoke Revision
         * @description Emergency-stop an exact schedule revision with durable reason.
         */
        post: operations["revoke_revision_api__organization_id__schedules__schedule_id__revisions__revision__revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Knowledgebases */
        get: operations["list_knowledgebases_api__organization_id__knowledgebases_get"];
        put?: never;
        /**
         * Create Knowledgebase
         * @description Define a knowledgebase. No vendor is assumed; the caller names one.
         */
        post: operations["create_knowledgebase_api__organization_id__knowledgebases_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Knowledgebase
         * @description Return one organization-owned knowledgebase without disclosing others.
         */
        get: operations["get_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__get"];
        put?: never;
        post?: never;
        /** Delete Knowledgebase */
        delete: operations["delete_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__delete"];
        options?: never;
        head?: never;
        /** Update Knowledgebase */
        patch: operations["update_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__patch"];
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}/reindex": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Knowledgebase Reindex Status */
        get: operations["get_knowledgebase_reindex_status_api__organization_id__knowledgebases__knowledgebase_id__reindex_get"];
        put?: never;
        /** Reindex Knowledgebase */
        post: operations["reindex_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__reindex_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/grants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Grant Knowledgebase
         * @description Give an agent access. Omitting `access` grants READ, never write.
         */
        post: operations["grant_knowledgebase_api__organization_id__knowledgebases_grants_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/grants/{agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Grants
         * @description What this agent may read and write. The whole of its knowledge surface.
         */
        get: operations["list_grants_api__organization_id__knowledgebases_grants__agent_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/grants/{agent_id}/{knowledgebase_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke Knowledgebase */
        delete: operations["revoke_knowledgebase_api__organization_id__knowledgebases_grants__agent_id___knowledgebase_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Ingestions
         * @description Recent jobs for this knowledgebase, newest first.
         */
        get: operations["list_ingestions_api__organization_id__knowledgebases__knowledgebase_id__ingestions_get"];
        put?: never;
        /**
         * Submit Ingestion
         * @description Queue a document. 202, because the work has not happened yet.
         *
         *     Idempotent on the document's identity: submitting the same document while
         *     a job for it is still pending or running returns that job rather than
         *     queueing a second one.
         */
        post: operations["submit_ingestion_api__organization_id__knowledgebases__knowledgebase_id__ingestions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/corpus": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Corpus Imports */
        get: operations["list_corpus_imports_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus_get"];
        put?: never;
        /**
         * Start Corpus Import
         * @description Sweep a storage prefix into this knowledgebase.
         *
         *     Returns immediately with an import to watch. The sweep enumerates the
         *     prefix and files one ingestion job per object; nothing is read until a
         *     worker picks each job up.
         *
         *     **Safe to re-run.** Each object's identity is its storage address, so a
         *     second import replaces changed documents and skips unchanged ones rather
         *     than growing a second copy of the corpus. That is also what makes a crashed
         *     sweep recoverable — it is simply run again.
         */
        post: operations["start_corpus_import_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/corpus/{import_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Corpus Import
         * @description One import, including what it skipped and why.
         */
        get: operations["get_corpus_import_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus__import_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/corpus/{import_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Corpus Import
         * @description Stop a sweep. Jobs it already filed keep running.
         *
         *     Cancelling the sweep does not cancel the documents it found — those are
         *     real work already accepted. Cancel them individually if that is what you
         *     want.
         */
        post: operations["cancel_corpus_import_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus__import_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Ingestion */
        get: operations["get_ingestion_api__organization_id__knowledgebases__knowledgebase_id__ingestions__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/{job_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Ingestion
         * @description Stop a job that has not finished.
         *
         *     A running job may still complete the document it is on — cancelling stops
         *     the job, not the write in flight. Promising otherwise would be a guarantee
         *     this cannot keep, and the write is idempotent either way.
         */
        post: operations["cancel_ingestion_api__organization_id__knowledgebases__knowledgebase_id__ingestions__job_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-stats/count": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Agent Stats Count
         * @description Get count of agents, optionally filtered by status.
         *
         *     Args:
         *         organization_id (UUID): Organization ID.
         *         status (list[str] | None): Optional list of agent statuses to filter.
         *         current_user (CurrentUserSchema): Authenticated user.
         *
         *     Returns:
         *         int: Count of agents.
         */
        get: operations["agent_stats_count_api__organization_id__agent_stats_count_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/phone-numbers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Phone Numbers */
        get: operations["list_phone_numbers_api_phone_numbers_get"];
        put?: never;
        /** Create Phone Number */
        post: operations["create_phone_number_api_phone_numbers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/phone-numbers/{phone_number_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Phone Number */
        get: operations["get_phone_number_api_phone_numbers__phone_number_id__get"];
        put?: never;
        post?: never;
        /** Delete Phone Number */
        delete: operations["delete_phone_number_api_phone_numbers__phone_number_id__delete"];
        options?: never;
        head?: never;
        /** Update Phone Number */
        patch: operations["update_phone_number_api_phone_numbers__phone_number_id__patch"];
        trace?: never;
    };
    "/api/calls": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Calls */
        get: operations["list_calls_api_calls_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/calls/{call_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Call */
        get: operations["get_call_api_calls__call_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Call
         * @description Accept asynchronous deletion of one owned call from Eylo
         */
        delete: operations["delete_call_api_calls__call_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Templates */
        get: operations["list_templates_api_templates_get"];
        put?: never;
        /** Create Template */
        post: operations["create_template_api_templates_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Template */
        get: operations["get_template_api_templates__template_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}/draft": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Template Draft */
        patch: operations["update_template_draft_api_templates__template_id__draft_patch"];
        trace?: never;
    };
    "/api/templates/{template_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Template */
        post: operations["preview_template_api_templates__template_id__preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish Template */
        post: operations["publish_template_api_templates__template_id__publish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}/revisions/{revision}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Template Revision */
        get: operations["get_template_revision_api_templates__template_id__revisions__revision__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}/revisions/{revision}/render": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Render Template Revision */
        post: operations["render_template_revision_api_templates__template_id__revisions__revision__render_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}/withdraw": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Withdraw Template */
        post: operations["withdraw_template_api_templates__template_id__withdraw_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}/revisions/{revision}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revoke Template Revision */
        post: operations["revoke_template_revision_api_templates__template_id__revisions__revision__revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/telephony-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Telephony Configs */
        get: operations["list_telephony_configs_api_telephony_configs_get"];
        put?: never;
        /** Create Telephony Config */
        post: operations["create_telephony_config_api_telephony_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/telephony-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Telephony Config */
        get: operations["get_telephony_config_api_telephony_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Telephony Config */
        delete: operations["delete_telephony_config_api_telephony_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Telephony Config */
        patch: operations["update_telephony_config_api_telephony_configs__config_id__patch"];
        trace?: never;
    };
    "/api/telephony-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Telephony Config */
        post: operations["verify_telephony_config_api_telephony_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/telephony-configs/{provider_config_id}/numbers/available": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search Available Numbers
         * @description Search for available phone numbers from a telephony provider.
         */
        get: operations["search_available_numbers_api_telephony_configs__provider_config_id__numbers_available_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/telephony-configs/{provider_config_id}/numbers/purchase": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Purchase Number
         * @description Persist a stable intent before one exact charged carrier purchase.
         */
        post: operations["purchase_number_api_telephony_configs__provider_config_id__numbers_purchase_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/events/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Event Health
         * @description Return tenant-safe backlog/failure facts plus process registrations.
         */
        get: operations["get_event_health_api_events_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Members */
        get: operations["list_members_api__organization_id__members_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/members/{member_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Member */
        get: operations["get_member_api__organization_id__members__member_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List User Sessions */
        get: operations["list_user_sessions_api__organization_id__sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/sessions/{user_session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get User Session */
        get: operations["get_user_session_api__organization_id__sessions__user_session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/sessions/{user_session_id}/timeline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get User Session Timeline */
        get: operations["get_user_session_timeline_api__organization_id__sessions__user_session_id__timeline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-vendors": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Curated Vendors
         * @description Browse the curated vendors this deployment carries.
         */
        get: operations["list_curated_vendors_api__organization_id__curated_vendors_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-vendors/{vendor}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Curated Vendor
         * @description One curated vendor and the tools it offers.
         */
        get: operations["get_curated_vendor_api__organization_id__curated_vendors__vendor__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-vendors/{vendor}/install": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Install Curated Vendor
         * @description Install one curated vendor for this organization.
         */
        post: operations["install_curated_vendor_api__organization_id__curated_vendors__vendor__install_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-integrations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Curated Installations
         * @description Curated vendors this organization has installed.
         */
        get: operations["list_curated_installations_api__organization_id__curated_integrations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/aggregate/curated-connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Curated Connection Aggregates
         * @description Connections plus resolved owners for operator-facing collection views.
         */
        get: operations["list_curated_connection_aggregates_api__organization_id__aggregate_curated_connections_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Curated Connections
         * @description Connections that authorize curated vendors. Credentials are never returned.
         */
        get: operations["list_curated_connections_api__organization_id__curated_connections_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-connections/{connection_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Curated Connection
         * @description Clear and remove one curated connection from this organization.
         */
        delete: operations["delete_curated_connection_api__organization_id__curated_connections__connection_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-vendors/{vendor}/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Curated Vendor Tools
         * @description Curated tools for one installed vendor, with their live policy.
         */
        get: operations["list_curated_vendor_tools_api__organization_id__curated_vendors__vendor__tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-vendors/{vendor}/tools/{tool_name}/execution-mode": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Curated Tool Execution Mode
         * @description Set operator policy for one curated tool.
         *
         *     Policy is read live at execution, so a change here takes effect on the next
         *     call rather than when an agent is next rebound.
         */
        put: operations["set_curated_tool_execution_mode_api__organization_id__curated_vendors__vendor__tools__tool_name__execution_mode_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-vendors/{vendor}/connect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Connect Curated Vendor
         * @description Store a directly-entered credential for an api_key or basic vendor.
         */
        post: operations["connect_curated_vendor_api__organization_id__curated_vendors__vendor__connect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/curated-vendors/{vendor}/authorize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Begin Curated Authorization
         * @description Begin an OAuth flow and return the provider consent URL.
         */
        post: operations["begin_curated_authorization_api__organization_id__curated_vendors__vendor__authorize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/curated-tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Agent Curated Tools
         * @description List curated tools granted to an Agent draft.
         */
        get: operations["list_agent_curated_tools_api__organization_id__agents__agent_id__curated_tools_get"];
        /**
         * Replace Agent Curated Tools
         * @description Replace the exact curated-tool selection on an Agent draft.
         */
        put: operations["replace_agent_curated_tools_api__organization_id__agents__agent_id__curated_tools_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agents/{agent_id}/curated-tools/{vendor}/{tool_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Grant Agent Curated Tool
         * @description Grant one installed curated tool to an Agent draft.
         */
        post: operations["grant_agent_curated_tool_api__organization_id__agents__agent_id__curated_tools__vendor___tool_name__post"];
        /**
         * Revoke Agent Curated Tool
         * @description Remove one curated tool from an Agent draft.
         */
        delete: operations["revoke_agent_curated_tool_api__organization_id__agents__agent_id__curated_tools__vendor___tool_name__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Llm Configs */
        get: operations["list_llm_configs_api_llm_configs_get"];
        put?: never;
        /** Create Llm Config */
        post: operations["create_llm_config_api_llm_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/llm-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Llm Config */
        get: operations["get_llm_config_api_llm_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Llm Config */
        delete: operations["delete_llm_config_api_llm_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Llm Config */
        patch: operations["update_llm_config_api_llm_configs__config_id__patch"];
        trace?: never;
    };
    "/api/llm-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Llm Config */
        post: operations["verify_llm_config_api_llm_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/capabilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Capabilities */
        get: operations["get_capabilities_api_capabilities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/provider-onboarding/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Catalog
         * @description Return the complete provider form contract for an authenticated member.
         */
        get: operations["get_catalog_api_provider_onboarding_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/tools/system-catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List System Tools Catalog
         * @description List all available system tools from the code registry.
         *
         *     Returns virtual tool objects with deterministic UUIDs scoped to the org.
         *     These can be mapped to agents via the agent-tool assignment API.
         */
        get: operations["list_system_tools_catalog_api__organization_id__tools_system_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/tools/provider-catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Provider Tools Catalog
         * @description List Agent tools enabled by one provider capability.
         *
         *     The projection is independent of current configuration readiness so an
         *     operator can understand what the capability unlocks before configuring it.
         */
        get: operations["list_provider_tools_catalog_api__organization_id__tools_provider_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tools */
        get: operations["list_tools_api__organization_id__tools_get"];
        put?: never;
        /** Create Tool */
        post: operations["create_tool_api__organization_id__tools_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/tools/{tool_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Tool */
        get: operations["get_tool_api__organization_id__tools__tool_id__get"];
        /** Update Tool */
        put: operations["update_tool_api__organization_id__tools__tool_id__put"];
        post?: never;
        /** Delete Tool */
        delete: operations["delete_tool_api__organization_id__tools__tool_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/tools/{tool_id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish Tool */
        post: operations["publish_tool_api__organization_id__tools__tool_id__publish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/tools/{tool_id}/withdraw": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Withdraw Tool */
        post: operations["withdraw_tool_api__organization_id__tools__tool_id__withdraw_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/tools/{tool_id}/revisions/{revision}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revoke Tool */
        post: operations["revoke_tool_api__organization_id__tools__tool_id__revisions__revision__revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/aggregate/conversations/{conversation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Conversation Aggregate
         * @description Get a single conversation with all related data (contact, agents, messages, participants).
         *
         *     This endpoint returns denormalized conversation data in a single response,
         *     eliminating the need for multiple API calls to fetch related entities.
         *
         *     Path: /api/{org_id}/aggregate/conversations/{conversation_id}
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         conversation_id (UUID): The ID of the conversation
         *         include_messages (bool): Whether to include messages (default: True)
         *         message_limit (int): Maximum number of messages to return (default: 50, max: 500)
         *         include_participants (bool): Whether to include participants (default: True)
         *         current_user: The authenticated user
         *
         *     Returns:
         *     -------
         *         ConversationAggregateResponse: Conversation with all related data
         */
        get: operations["get_conversation_aggregate_api__organization_id__aggregate_conversations__conversation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/aggregate/conversations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get Conversations Aggregate Bulk
         * @description Get multiple conversations with all related data in a single request.
         *
         *     This endpoint is optimized for bulk fetching of conversation aggregates,
         *     using efficient database queries to minimize round-trips.
         *
         *     Path: POST /api/{org_id}/aggregate/conversations
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         request (ConversationAggregateBulkRequest): Bulk request with conversation IDs and options
         *         current_user: The authenticated user
         *
         *     Returns:
         *     -------
         *         ConversationAggregateBulkResponse: List of conversations with related data
         */
        post: operations["get_conversations_aggregate_bulk_api__organization_id__aggregate_conversations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/conversations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Conversations
         * @description List conversations with pagination for a specific user.
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         user_id (UUID): The ID of the user
         *         pagination (PaginationParams): Pagination parameters
         *         sort (str, optional): Sort order, either 'asc' or 'desc'. Defaults to 'desc'.
         *
         *     Returns:
         *     -------
         *         ConversationsPaginated: The paginated conversations response
         */
        get: operations["list_conversations_api__organization_id__conversations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/conversations/{conversation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Conversation
         * @description Get a conversation by ID.
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         conversation_id (UUID): The ID of the conversation to get
         *
         *     Returns:
         *     -------
         *         ConversationApiResponseSchema: The conversation response with status
         */
        get: operations["get_conversation_api__organization_id__conversations__conversation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/conversations/{conversation_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Conversation Messages
         * @description Get paginated messages for a conversation.
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         conversation_id (UUID): UUID of the conversation
         *         pagination: Pagination parameters (page and limit)
         *
         *     Returns:
         *     -------
         *         ConversationMessagesPaginated: Paginated list of messages with status and error information
         */
        get: operations["get_conversation_messages_api__organization_id__conversations__conversation_id__messages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/conversations/{conversation_id}/participants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Conversation Participants
         * @description Get paginated participants for a conversation.
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         conversation_id (UUID): UUID of the conversation
         *         pagination: Pagination parameters (page and limit)
         *
         *     Returns:
         *     -------
         *         ConversationParticipantsPaginated: Paginated list of messages with status and error information
         */
        get: operations["get_conversation_participants_api__organization_id__conversations__conversation_id__participants_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Conversation Messages
         * @description Get paginated messages for a conversation.
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         pagination: Pagination parameters (page and limit)
         *
         *     Returns:
         *     -------
         *         ConversationMessagesPaginated: Paginated list of messages with status and error information
         */
        get: operations["list_conversation_messages_api__organization_id__messages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/messages/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Message Feedback
         * @description Submit feedback for a message.
         */
        post: operations["submit_message_feedback_api__organization_id__messages_feedback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/participants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Conversation Participants
         * @description Get paginated participants for a conversation.
         *
         *     Args:
         *     ----
         *         organization_id (UUID): The ID of the organization
         *         pagination: Pagination parameters (page and limit)
         *
         *     Returns:
         *     -------
         *         ConversationParticipantsPaginated: Paginated list of messages with status and error information
         */
        get: operations["list_conversation_participants_api__organization_id__participants_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Me
         * @description Get Current User Profile.
         */
        get: operations["get_me_api_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/widget-invitations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Issue Invitation */
        post: operations["issue_invitation_api__organization_id__widget_invitations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/api-keys": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Api Keys
         * @description List API Keys.
         */
        get: operations["list_api_keys_api_auth_api_keys_get"];
        put?: never;
        /**
         * Create Api Key
         * @description Create API Key.
         */
        post: operations["create_api_key_api_auth_api_keys_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/api-keys/{api_key_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Revoke Api Key
         * @description Revoke API Key.
         */
        delete: operations["revoke_api_key_api_auth_api_keys__api_key_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/contacts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Contacts
         * @description Get a connection by Connection ID
         */
        get: operations["list_contacts_api__organization_id__contacts_get"];
        put?: never;
        /**
         * Create Contact
         * @description Create a new connection
         */
        post: operations["create_contact_api__organization_id__contacts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/contacts/{contact_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Contact
         * @description Get contact by ID
         */
        get: operations["get_contact_api__organization_id__contacts__contact_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Contact
         * @description Fence an owned contact and accept asynchronous Eylo deletion
         */
        delete: operations["delete_contact_api__organization_id__contacts__contact_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Contact
         * @description Patch maintained fields on an owned contact
         */
        patch: operations["update_contact_api__organization_id__contacts__contact_id__patch"];
        trace?: never;
    };
    "/api/deletions/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Deletion Job
         * @description Return one owned content-free deletion monitor or the same 404.
         */
        get: operations["get_deletion_job_api_deletions__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/analytics/conversations/created-per-agent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Conversations Created Per Agent */
        get: operations["get_conversations_created_per_agent_api__organization_id__analytics_conversations_created_per_agent_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/analytics/{entity}/created": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Entity Created */
        get: operations["get_entity_created_api__organization_id__analytics__entity__created_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/voice-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Voice Configs */
        get: operations["list_voice_configs_api__organization_id__voice_configs_get"];
        put?: never;
        /** Create Voice Config */
        post: operations["create_voice_config_api__organization_id__voice_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/voice-configs/{voice_config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Voice Config */
        get: operations["get_voice_config_api__organization_id__voice_configs__voice_config_id__get"];
        put?: never;
        post?: never;
        /** Delete Voice Config */
        delete: operations["delete_voice_config_api__organization_id__voice_configs__voice_config_id__delete"];
        options?: never;
        head?: never;
        /** Update Voice Config */
        patch: operations["update_voice_config_api__organization_id__voice_configs__voice_config_id__patch"];
        trace?: never;
    };
    "/api/{organization_id}/voice-configs/{voice_config_id}/compatibility": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Voice Config Compatibility */
        get: operations["get_voice_config_compatibility_api__organization_id__voice_configs__voice_config_id__compatibility_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/voice-configs/{voice_config_id}/sections/{section}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Voice Config Section */
        patch: operations["patch_voice_config_section_api__organization_id__voice_configs__voice_config_id__sections__section__patch"];
        trace?: never;
    };
    "/api/stt-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Stt Configs */
        get: operations["list_stt_configs_api_stt_configs_get"];
        put?: never;
        /** Create Stt Config */
        post: operations["create_stt_config_api_stt_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stt-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Stt Config */
        get: operations["get_stt_config_api_stt_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Stt Config */
        delete: operations["delete_stt_config_api_stt_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Stt Config */
        patch: operations["update_stt_config_api_stt_configs__config_id__patch"];
        trace?: never;
    };
    "/api/stt-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Stt Config */
        post: operations["verify_stt_config_api_stt_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tts-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tts Configs */
        get: operations["list_tts_configs_api_tts_configs_get"];
        put?: never;
        /** Create Tts Config */
        post: operations["create_tts_config_api_tts_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tts-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Tts Config */
        get: operations["get_tts_config_api_tts_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Tts Config */
        delete: operations["delete_tts_config_api_tts_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Tts Config */
        patch: operations["update_tts_config_api_tts_configs__config_id__patch"];
        trace?: never;
    };
    "/api/tts-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Tts Config */
        post: operations["verify_tts_config_api_tts_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/realtime-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Realtime Configs */
        get: operations["list_realtime_configs_api_realtime_configs_get"];
        put?: never;
        /** Create Realtime Config */
        post: operations["create_realtime_config_api_realtime_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/realtime-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Realtime Config */
        get: operations["get_realtime_config_api_realtime_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Realtime Config */
        delete: operations["delete_realtime_config_api_realtime_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Realtime Config */
        patch: operations["update_realtime_config_api_realtime_configs__config_id__patch"];
        trace?: never;
    };
    "/api/realtime-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Realtime Config */
        post: operations["verify_realtime_config_api_realtime_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/webrtc-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Webrtc Configs */
        get: operations["list_webrtc_configs_api_webrtc_configs_get"];
        put?: never;
        /** Create Webrtc Config */
        post: operations["create_webrtc_config_api_webrtc_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/webrtc-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Webrtc Config */
        get: operations["get_webrtc_config_api_webrtc_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Webrtc Config */
        delete: operations["delete_webrtc_config_api_webrtc_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Webrtc Config */
        patch: operations["update_webrtc_config_api_webrtc_configs__config_id__patch"];
        trace?: never;
    };
    "/api/webrtc-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Webrtc Config */
        post: operations["verify_webrtc_config_api_webrtc_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/email-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Email Configs */
        get: operations["list_email_configs_api_email_configs_get"];
        put?: never;
        /** Create Email Config */
        post: operations["create_email_config_api_email_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/email-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Email Config */
        get: operations["get_email_config_api_email_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Email Config */
        delete: operations["delete_email_config_api_email_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Email Config */
        patch: operations["update_email_config_api_email_configs__config_id__patch"];
        trace?: never;
    };
    "/api/email-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Email Config */
        post: operations["verify_email_config_api_email_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/storage-configs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Storage Configs */
        get: operations["list_storage_configs_api_storage_configs_get"];
        put?: never;
        /** Create Storage Config */
        post: operations["create_storage_config_api_storage_configs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/storage-configs/{config_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Storage Config */
        get: operations["get_storage_config_api_storage_configs__config_id__get"];
        put?: never;
        post?: never;
        /** Delete Storage Config */
        delete: operations["delete_storage_config_api_storage_configs__config_id__delete"];
        options?: never;
        head?: never;
        /** Update Storage Config */
        patch: operations["update_storage_config_api_storage_configs__config_id__patch"];
        trace?: never;
    };
    "/api/storage-configs/{config_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Storage Config */
        post: operations["verify_storage_config_api_storage_configs__config_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/organizations/{organization_id}/conversations/{conversation_id}/recordings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Recordings
         * @description List all voice recordings for a conversation.
         *
         *     Returns recording metadata with authenticated application download URLs.
         */
        get: operations["list_recordings_api_organizations__organization_id__conversations__conversation_id__recordings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/organizations/{organization_id}/conversations/{conversation_id}/recordings/{recording_id}/{track}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download Recording Track
         * @description Stream one organization-owned recording track through bearer auth.
         */
        get: operations["download_recording_track_api_organizations__organization_id__conversations__conversation_id__recordings__recording_id___track__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/voice-sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Voice Sessions
         * @description List voice transcript sessions visible to the current organization.
         */
        get: operations["list_voice_sessions_api__organization_id__voice_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/voice-sessions/{voice_session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Voice Session
         * @description Get one voice transcript session with ordered timeline segments.
         */
        get: operations["get_voice_session_api__organization_id__voice_sessions__voice_session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/conversations/{conversation_id}/voice-session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Voice Session For Conversation
         * @description Get the voice transcript session attached to a conversation.
         */
        get: operations["get_voice_session_for_conversation_api__organization_id__conversations__conversation_id__voice_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Agent Swarm
         * @description Create a new agent swarm for the current user's organization.
         *
         *     Args:
         *         organization_id (UUID): The ID of the organization.
         *         request (AgentSwarmCreate): The data for creating a new agent swarm.
         *         current_user (CurrentUserSchema): The authenticated user making the request.
         *
         *     Returns:
         *         AgentSwarmResponseSchema: The created agent swarm's data.
         *
         *     Raises:
         *         HTTPException: If there's a duplicate agent swarm or other creation error.
         */
        post: operations["create_agent_swarm_api__organization_id__agent_swarm_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Agent Swarms
         * @description List all agent swarms for the current user's organization.
         *
         *     Args:
         *         organization_id (UUID): The ID of the organization.
         *         current_user (CurrentUserSchema): The authenticated user making the request.
         *
         *     Returns:
         *         list[AgentSwarmResponseSchema]: List of agent swarms.
         */
        get: operations["list_agent_swarms_api__organization_id__agent_swarm_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/{swarm_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Update Agent Swarm
         * @description Update an existing agent swarm.
         *
         *     Args:
         *         organization_id (UUID): The ID of the organization.
         *         swarm_id (UUID): The ID of the swarm to update.
         *         request (AgentSwarmCreateRequestSchema): The updated swarm data.
         *         current_user (CurrentUserSchema): The authenticated user making the request.
         *
         *     Returns:
         *         AgentSwarmResponseSchema: The updated agent swarm's data.
         *
         *     Raises:
         *         HTTPException: If there's an error updating the swarm.
         */
        put: operations["update_agent_swarm_api__organization_id__agent_swarm__swarm_id__put"];
        post?: never;
        /**
         * Delete Agent Swarm
         * @description Delete an existing agent swarm.
         *
         *     Args:
         *         organization_id (UUID): The ID of the organization.
         *         swarm_id (UUID): The ID of the swarm to delete.
         *         current_user (CurrentUserSchema): The authenticated user making the request.
         *
         *     Returns:
         *         dict: Confirmation message.
         *
         *     Raises:
         *         HTTPException: If there's an error deleting the swarm.
         */
        delete: operations["delete_agent_swarm_api__organization_id__agent_swarm__swarm_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/{swarm_id}/add-agent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Add Agent To Swarm
         * @description Add an agent to an existing swarm.
         *
         *     Args:
         *         organization_id (UUID): The ID of the organization.
         *         swarm_id (UUID): The ID of the swarm to add the agent to.
         *         request (AgentToolRequest): The details of the agent to add.
         *         current_user (CurrentUserSchema): The authenticated user making the request.
         *
         *     Returns:
         *         AgentResponseSchema: The updated agent's data.
         *
         *     Raises:
         *         HTTPException: If there's an error adding the agent to the swarm.
         */
        post: operations["add_agent_to_swarm_api__organization_id__agent_swarm__swarm_id__add_agent_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/{swarm_id}/agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Agents In Swarm
         * @description List all agents in a specific swarm.
         *
         *     Args:
         *         organization_id (UUID): The ID of the organization.
         *         swarm_id (UUID): The ID of the swarm to list agents from.
         *         current_user (CurrentUserSchema): The authenticated user making the request.
         *
         *     Returns:
         *         list[AgentSwarmMappingResponseSchema]: List of agents in the swarm.
         *
         *     Raises:
         *         HTTPException: If there's an error retrieving the agents.
         */
        get: operations["list_agents_in_swarm_api__organization_id__agent_swarm__swarm_id__agents_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/{swarm_id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Publish Agent Swarm
         * @description Publish the complete swarm draft as one immutable topology revision.
         */
        put: operations["publish_agent_swarm_api__organization_id__agent_swarm__swarm_id__publish_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/{swarm_id}/unpublish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Withdraw Agent Swarm
         * @description Withdraw the alias while existing exact topology refs remain readable.
         */
        put: operations["withdraw_agent_swarm_api__organization_id__agent_swarm__swarm_id__unpublish_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/{swarm_id}/revisions/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Revoke Agent Swarm Revision
         * @description Emergency-revoke one exact topology and request run cancellation.
         */
        post: operations["revoke_agent_swarm_revision_api__organization_id__agent_swarm__swarm_id__revisions_revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/agent-swarm/{swarm_id}/remove-agent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Remove Agent From Swarm
         * @description Remove an agent from an existing swarm.
         *
         *     Args:
         *         organization_id (UUID): The ID of the organization.
         *         swarm_id (UUID): The ID of the swarm to remove the agent from.
         *         agent_id (UUID): The ID of the agent to remove.
         *         current_user (CurrentUserSchema): The authenticated user making the request.
         *
         *     Returns:
         *         dict: Confirmation message.
         *
         *     Raises:
         *         HTTPException: If there's an error removing the agent from the swarm.
         */
        delete: operations["remove_agent_from_swarm_api__organization_id__agent_swarm__swarm_id__remove_agent_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Campaigns
         * @description List campaigns for an organization
         */
        get: operations["list_campaigns_api__organization_id__campaigns_get"];
        put?: never;
        /**
         * Create Campaign
         * @description Create a new campaign
         */
        post: operations["create_campaign_api__organization_id__campaigns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Campaign
         * @description Get campaign details
         */
        get: operations["get_campaign_api__organization_id__campaigns__campaign_id__get"];
        /**
         * Update Campaign
         * @description Update a campaign (DRAFT or PAUSED only)
         */
        put: operations["update_campaign_api__organization_id__campaigns__campaign_id__put"];
        post?: never;
        /**
         * Delete Campaign
         * @description Delete a campaign (DRAFT or CANCELED only)
         */
        delete: operations["delete_campaign_api__organization_id__campaigns__campaign_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/preparation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Campaign Preparation
         * @description Inspect warning-only audience preparation without filtering contacts
         */
        get: operations["get_campaign_preparation_api__organization_id__campaigns__campaign_id__preparation_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Campaign
         * @description Start a campaign (DRAFT/PAUSED → RUNNING)
         */
        post: operations["start_campaign_api__organization_id__campaigns__campaign_id__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Pause Campaign
         * @description Pause a running campaign
         */
        post: operations["pause_campaign_api__organization_id__campaigns__campaign_id__pause_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Campaign
         * @description Cancel a campaign
         */
        post: operations["cancel_campaign_api__organization_id__campaigns__campaign_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/revisions/{revision}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Revoke Campaign Revision
         * @description Emergency-revoke an exact campaign revision
         */
        post: operations["revoke_campaign_revision_api__organization_id__campaigns__campaign_id__revisions__revision__revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/contacts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Contacts
         * @description List contacts in a campaign
         */
        get: operations["list_contacts_api__organization_id__campaigns__campaign_id__contacts_get"];
        put?: never;
        /**
         * Upload Contacts
         * @description Upload contacts to a campaign
         */
        post: operations["upload_contacts_api__organization_id__campaigns__campaign_id__contacts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/contacts/select": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Select Contacts
         * @description Add existing contacts to a campaign by their IDs
         */
        post: operations["select_contacts_api__organization_id__campaigns__campaign_id__contacts_select_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/{organization_id}/campaigns/{campaign_id}/analytics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Analytics
         * @description Get campaign analytics and outcome distribution
         */
        get: operations["get_analytics_api__organization_id__campaigns__campaign_id__analytics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/voice/outbound": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Outbound Call
         * @description Initiates an outbound call via the configured telephony provider.
         *
         *     This endpoint is used by the outbound_call system tool to trigger calls.
         *     It expects a JSON body with:
         *     - to_number: Target phone number
         *     - agent_id: UUID of the agent
         *     - initial_message: Optional first message
         */
        post: operations["outbound_call_api_voice_outbound_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/waitlist": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Waitlist
         * @description Add a user to the waitlist.
         */
        post: operations["waitlist_api_auth_waitlist_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Register
         * @description Add a user to the waitlist.
         */
        post: operations["register_api_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Authenticate a user and return a JWT TokenResponseSchema.
         */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description Complete stateless logout; clients discard their bearer token locally.
         */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/invite": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Invite Member
         * @description Invite a member to the authenticated member's organization.
         */
        post: operations["invite_member_api_auth_invite_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/accept-invite": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Invite
         * @description Accept an organization invite and create a new member.
         */
        post: operations["accept_invite_api_auth_accept_invite_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/forgot-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Forgot Password
         * @description Request a password reset link.
         */
        post: operations["forgot_password_api_auth_forgot_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/reset-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reset Password
         * @description Reset a member's password using a reset token.
         */
        post: operations["reset_password_api_auth_reset_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/public/session/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Validate Session
         * @description Validate a session using auth session token and verify all relationships.
         */
        post: operations["validate_session_api_public_session_validate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/public/widget-invitations/exchange": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Exchange Invitation */
        post: operations["exchange_invitation_api_public_widget_invitations_exchange_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/public/widget-development/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Development Session
         * @description Issue a real contact session using server-owned local configuration.
         */
        post: operations["create_development_session_api_public_widget_development_session_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/oauth/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Complete Curated Authorization
         * @description Handle the provider redirect and store the resulting connection.
         */
        get: operations["complete_curated_authorization_api_oauth_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/telephony/webhooks/{provider}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Status Callback */
        post: operations["status_callback_api_telephony_webhooks__provider__status_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/widget/{organization_id}/curated-connections/capabilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Widget List Curated Capabilities
         * @description List curated tools pinned to one available published Agent revision.
         */
        get: operations["widget_list_curated_capabilities_api_widget__organization_id__curated_connections_capabilities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/widget/{organization_id}/curated-connections/bulk-capabilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Widget List Bulk Curated Capabilities
         * @description List curated capability groups for the visible Agent catalogue.
         */
        post: operations["widget_list_bulk_curated_capabilities_api_widget__organization_id__curated_connections_bulk_capabilities_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/widget/{organization_id}/curated-connections/oauth/initiate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Widget Initiate Curated Oauth
         * @description Return the consent URL for a vendor this contact's agent actually uses.
         */
        get: operations["widget_initiate_curated_oauth_api_widget__organization_id__curated_connections_oauth_initiate_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/widget/{organization_id}/curated-connections/{vendor}/connect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Widget Connect Curated Credential
         * @description Bind a direct credential to the current contact, never a request-supplied id.
         */
        post: operations["widget_connect_curated_credential_api_widget__organization_id__curated_connections__vendor__connect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/widget/{organization_id}/conversations/{conversation_id}/knowledgebases/file-upload-capability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Widget Knowledge File Upload Capability
         * @description Tell the widget whether the exact pinned Agent revision permits files.
         */
        get: operations["get_widget_knowledge_file_upload_capability_api_widget__organization_id__conversations__conversation_id__knowledgebases_file_upload_capability_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/widget/{organization_id}/conversations/{conversation_id}/knowledgebases/files": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Upload Widget Knowledge File
         * @description Extract one bounded file and enqueue ordinary durable ingestion.
         */
        post: operations["upload_widget_knowledge_file_api_widget__organization_id__conversations__conversation_id__knowledgebases_files_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/widget/{organization_id}/conversations/{conversation_id}/knowledgebases/ingestions/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Widget Knowledge Ingestion
         * @description Return the durable state of one upload accepted in this conversation.
         */
        get: operations["get_widget_knowledge_ingestion_api_widget__organization_id__conversations__conversation_id__knowledgebases_ingestions__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Root
         * @description Root endpoint for the Eylo Server.
         */
        get: operations["read_root__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health Check
         * @description Health check endpoint for the Eylo Server.
         */
        get: operations["health_check_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AcceptInviteRequestSchema
         * @description Request schema for accepting an organization invite.
         */
        AcceptInviteRequestSchema: {
            /**
             * Token
             * @description Invite JWT token
             */
            token: string;
            /**
             * Password
             * @description New member password
             */
            password: string;
        };
        /** AgentBackgroundAgentCreate */
        AgentBackgroundAgentCreate: {
            /**
             * Background Agent Id
             * Format: uuid
             * @description The background agent.
             */
            background_agent_id: string;
            /** Expected Draft Version */
            expected_draft_version: number;
        };
        /** AgentBackgroundAgentInDb */
        AgentBackgroundAgentInDb: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Created At
             * Format: date-time
             * @description Record creation timestamp
             */
            created_at?: string;
            /**
             * Updated At
             * Format: date-time
             * @description Record last update timestamp
             */
            updated_at?: string;
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /**
             * Background Agent Id
             * Format: uuid
             */
            background_agent_id: string;
            /**
             * Enabled
             * @default false
             */
            enabled: boolean;
        };
        /** AgentBackgroundAgentUpdate */
        AgentBackgroundAgentUpdate: {
            /**
             * Enabled
             * @description Whether this attachment dispatches.
             */
            enabled: boolean;
            /** Expected Draft Version */
            expected_draft_version: number;
        };
        /** AgentCreateRequestSchema */
        AgentCreateRequestSchema: {
            /** Name */
            name: string;
            /** Description */
            description?: string | null;
            /** @default CONVERSATIONAL */
            kind: components["schemas"]["AgentKind"];
            /** Llmproviderconfigid */
            llmProviderConfigId?: string | null;
            /** Emailproviderconfigid */
            emailProviderConfigId?: string | null;
            /** Webrtcproviderconfigid */
            webrtcProviderConfigId?: string | null;
            /** Voiceconfigid */
            voiceConfigId?: string | null;
            llmOverrides?: components["schemas"]["LLMOverridesSchema"];
            /** Rerankingproviderconfigid */
            rerankingProviderConfigId?: string | null;
            /** Memoryproviderconfigid */
            memoryProviderConfigId?: string | null;
            /**
             * Allowfileuploads
             * @default false
             */
            allowFileUploads: boolean;
            /** Fileuploadembeddingproviderconfigid */
            fileUploadEmbeddingProviderConfigId?: string | null;
            /** Instructiontemplateid */
            instructionTemplateId?: string | null;
        };
        /**
         * AgentEffectiveVoiceStackResponseSchema
         * @description Exact voice authority copied into the Agent's published revision.
         */
        AgentEffectiveVoiceStackResponseSchema: {
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Agentrevision */
            agentRevision?: number | null;
            state: components["schemas"]["AgentVoiceStackState"];
            voiceConfig?: components["schemas"]["AgentRevisionReferenceSchema"] | null;
            webrtcProvider?: components["schemas"]["AgentRevisionReferenceSchema"] | null;
            sttProvider?: components["schemas"]["AgentRevisionReferenceSchema"] | null;
            ttsProvider?: components["schemas"]["AgentRevisionReferenceSchema"] | null;
            realtimeProvider?: components["schemas"]["AgentRevisionReferenceSchema"] | null;
            storageProvider?: components["schemas"]["AgentRevisionReferenceSchema"] | null;
        };
        /**
         * AgentInputRequestKind
         * @description Kinds of explicit human response a run may await.
         * @enum {string}
         */
        AgentInputRequestKind: "input" | "approval";
        /** AgentInputRequestRead */
        AgentInputRequestRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["AgentInputRequestKind"];
            /** Prompt */
            prompt: string;
            /** Expected Response Schema */
            expected_response_schema: {
                [key: string]: unknown;
            };
            status: components["schemas"]["AgentInputRequestStatus"];
            response: components["schemas"]["JsonValue"] | null;
            answered_by_principal_kind: components["schemas"]["InitiatingPrincipalKind"] | null;
            /** Answered By Principal Id */
            answered_by_principal_id: string | null;
            /** State Revision */
            state_revision: number;
            /** Answered At */
            answered_at: string | null;
            /** Cancelled At */
            cancelled_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * AgentInputRequestStatus
         * @description No expiry exists: a request resolves only by answer or cancellation.
         * @enum {string}
         */
        AgentInputRequestStatus: "pending" | "answered" | "cancelled";
        /**
         * AgentInputResponseRequest
         * @description One explicit response to one still-pending input request.
         */
        AgentInputResponseRequest: {
            /** Expected State Revision */
            expected_state_revision: number;
            response: components["schemas"]["JsonValue"];
        };
        /**
         * AgentKind
         * @description What kind of runtime an agent has.
         *
         *     Exactly two values, deliberately. The separate-process long-running kind is
         *     a real concept with no runtime here, and adding the enum value before the
         *     runtime exists is the honest-surface violation this codebase keeps finding
         *     — a value an operator can select that does nothing. Add it when it is built.
         * @enum {string}
         */
        AgentKind: "CONVERSATIONAL" | "BACKGROUND";
        /** AgentPublishRequestSchema */
        AgentPublishRequestSchema: {
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** AgentResponseSchema */
        AgentResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * Format: uuid
             * @description Organization ID for the agent.
             */
            organizationId: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Llmproviderconfigid */
            llmProviderConfigId?: string | null;
            /** Llmproviderconfigrevision */
            llmProviderConfigRevision?: number | null;
            /** Emailproviderconfigid */
            emailProviderConfigId?: string | null;
            /** Emailproviderconfigrevision */
            emailProviderConfigRevision?: number | null;
            /** Webrtcproviderconfigid */
            webrtcProviderConfigId?: string | null;
            /** Webrtcproviderconfigrevision */
            webrtcProviderConfigRevision?: number | null;
            /** Voiceconfigid */
            voiceConfigId?: string | null;
            /** Voiceconfigrevision */
            voiceConfigRevision?: number | null;
            llmOverrides?: components["schemas"]["LLMOverridesSchema"];
            /** Rerankingproviderconfigid */
            rerankingProviderConfigId?: string | null;
            /** Rerankingproviderconfigrevision */
            rerankingProviderConfigRevision?: number | null;
            /** Memoryproviderconfigid */
            memoryProviderConfigId?: string | null;
            /** Memoryproviderconfigrevision */
            memoryProviderConfigRevision?: number | null;
            /**
             * Allowfileuploads
             * @default false
             */
            allowFileUploads: boolean;
            /** Fileuploadembeddingproviderconfigid */
            fileUploadEmbeddingProviderConfigId?: string | null;
            /** Fileuploadembeddingproviderconfigrevision */
            fileUploadEmbeddingProviderConfigRevision?: number | null;
            /** Instructiontemplateid */
            instructionTemplateId?: string | null;
            /** Description */
            description?: string | null;
            /** Webhook */
            webhook?: string | null;
            /**
             * @description Status of the agent.
             * @default DRAFT
             */
            status: components["schemas"]["AgentStatus"];
            /**
             * @description Conversational or background agent.
             * @default CONVERSATIONAL
             */
            kind: components["schemas"]["AgentKind"];
            /**
             * Implementation
             * @description Registry slug naming first-party code for a background agent. Null means prompt-only.
             */
            implementation?: string | null;
            /**
             * Prompt
             * @description Prompt configuration for the agent.
             */
            prompt?: {
                [key: string]: unknown;
            } | null;
            /**
             * Lifecycle
             * @default draft
             */
            lifecycle: string;
            /** Publishedrevision */
            publishedRevision?: number | null;
            /**
             * Draftversion
             * @default 1
             */
            draftVersion: number;
            /**
             * Draftdirty
             * @default true
             */
            draftDirty: boolean;
        };
        /** AgentRevisionReferenceSchema */
        AgentRevisionReferenceSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revision */
            revision: number;
        };
        /** AgentRevokeRequestSchema */
        AgentRevokeRequestSchema: {
            /** Revision */
            revision: number;
            /** Reason */
            reason: string;
        };
        /**
         * AgentRunCancelRequest
         * @description Optimistic cancellation command for one visible run revision.
         */
        AgentRunCancelRequest: {
            /** Expected State Revision */
            expected_state_revision: number;
        };
        /**
         * AgentRunCancellationDisposition
         * @description Whether cancellation completed locally or awaits the durable worker.
         * @enum {string}
         */
        AgentRunCancellationDisposition: "requested" | "cancelled";
        /** AgentRunCancellationRead */
        AgentRunCancellationRead: {
            disposition: components["schemas"]["AgentRunCancellationDisposition"];
            run: components["schemas"]["AgentRunRead"];
        };
        /**
         * AgentRunLifecycle
         * @description Execution/export lifecycle, separate from goal achievement.
         * @enum {string}
         */
        AgentRunLifecycle: "queued" | "running" | "waiting_for_input" | "waiting_for_approval" | "completed" | "failed" | "cancelled";
        /**
         * AgentRunOriginKind
         * @description Immutable V1 origins for an agent run.
         * @enum {string}
         */
        AgentRunOriginKind: "message" | "schedule_occurrence" | "objective";
        /**
         * AgentRunOutcome
         * @description Typed conclusion about whether the run achieved its goal.
         * @enum {string}
         */
        AgentRunOutcome: "achieved" | "unachievable" | "failed" | "cancelled" | "exhausted";
        /**
         * AgentRunRead
         * @description Organization-owned run state without internal engine identifiers.
         */
        AgentRunRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            initiating_principal_kind: components["schemas"]["InitiatingPrincipalKind"];
            /**
             * Initiating Principal Id
             * Format: uuid
             */
            initiating_principal_id: string;
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /** Agent Revision */
            agent_revision: number;
            origin_kind: components["schemas"]["AgentRunOriginKind"];
            /** Origin Message Id */
            origin_message_id: string | null;
            /** Origin Schedule Run Id */
            origin_schedule_run_id: string | null;
            lifecycle: components["schemas"]["AgentRunLifecycle"];
            outcome: components["schemas"]["AgentRunOutcome"] | null;
            /** Goal */
            goal: string;
            /** Result */
            result: {
                [key: string]: unknown;
            } | null;
            /** Outcome Reason */
            outcome_reason: string | null;
            /** Failure Summary */
            failure_summary: string | null;
            /** State Revision */
            state_revision: number;
            /** Started At */
            started_at: string | null;
            /** Waiting At */
            waiting_at: string | null;
            /** Cancellation Requested At */
            cancellation_requested_at: string | null;
            /** Cancelled At */
            cancelled_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            reservation: components["schemas"]["AgentRunReservationRead"] | null;
            /** Steps */
            steps: components["schemas"]["AgentRunStepRead"][];
            /** Input Requests */
            input_requests: components["schemas"]["AgentInputRequestRead"][];
        };
        /**
         * AgentRunReservationRead
         * @description Current pinned usage envelope shown with its organization-owned run.
         */
        AgentRunReservationRead: {
            /** Token Limit */
            token_limit: number;
            /** Time Limit Milliseconds */
            time_limit_milliseconds: number;
            /** Cost Limit Microunits */
            cost_limit_microunits: number;
            /** Used Tokens */
            used_tokens: number;
            /** Used Cost Microunits */
            used_cost_microunits: number;
            /** Active Milliseconds */
            active_milliseconds: number;
            /** Active */
            active: boolean;
            /** Active Since */
            active_since: string | null;
            /** Released At */
            released_at: string | null;
            exceeded_dimension: components["schemas"]["ExecutionBudgetDimension"] | null;
        };
        /**
         * AgentRunStepKind
         * @description Safe product projection kinds for workflow steps.
         * @enum {string}
         */
        AgentRunStepKind: "agent_turn" | "model_inference" | "tool" | "sandbox" | "artifact_export";
        /** AgentRunStepRead */
        AgentRunStepRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Step Key */
            step_key: string;
            kind: components["schemas"]["AgentRunStepKind"];
            status: components["schemas"]["AgentRunStepStatus"];
            /** Intent */
            intent: {
                [key: string]: unknown;
            };
            /** Safe Summary */
            safe_summary: string | null;
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            } | null;
            /** Artifact Refs */
            artifact_refs: unknown[];
            /** Started At */
            started_at: string | null;
            /** Completed At */
            completed_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * AgentRunStepStatus
         * @description Product/audit state for one run step.
         * @enum {string}
         */
        AgentRunStepStatus: "pending" | "running" | "completed" | "failed" | "cancelled";
        /**
         * AgentSortDirection
         * @enum {string}
         */
        AgentSortDirection: "asc" | "desc";
        /**
         * AgentSortField
         * @enum {string}
         */
        AgentSortField: "name" | "status" | "kind" | "created_at" | "updated_at";
        /**
         * AgentStatus
         * @description Enum representing the possible statuses of an agent.
         * @enum {string}
         */
        AgentStatus: "DRAFT" | "ACTIVE" | "INACTIVE" | "ARCHIVED";
        /**
         * AgentSummary
         * @description Lightweight agent representation for aggregates.
         */
        AgentSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Status */
            status: string;
        };
        /** AgentSwarmCreateRequestSchema */
        AgentSwarmCreateRequestSchema: {
            /** Name */
            name: string;
            /** Description */
            description?: string | null;
        };
        /** AgentSwarmMappingCreateRequestSchema */
        AgentSwarmMappingCreateRequestSchema: {
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Agentdescription */
            agentDescription?: string | null;
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** AgentSwarmMappingDeleteRequestSchema */
        AgentSwarmMappingDeleteRequestSchema: {
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** AgentSwarmMappingResponseSchema */
        AgentSwarmMappingResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * Format: uuid
             * @description Organization ID for the mapping.
             */
            organizationId: string;
            /**
             * Agentid
             * Format: uuid
             * @description Agent ID for the mapping.
             */
            agentId: string;
            /**
             * Swarmid
             * Format: uuid
             * @description Swarm ID for the mapping.
             */
            swarmId: string;
            /**
             * Agentdescription
             * @description Swarm-specific description for the agent.
             */
            agentDescription?: string | null;
        };
        /** AgentSwarmPublishRequestSchema */
        AgentSwarmPublishRequestSchema: {
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** AgentSwarmResponseSchema */
        AgentSwarmResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * Format: uuid
             * @description Organization ID for the agent swarm.
             */
            organizationId: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Description */
            description?: string | null;
            /**
             * Lifecycle
             * @default draft
             */
            lifecycle: string;
            /** Publishedrevision */
            publishedRevision?: number | null;
            /**
             * Draftversion
             * @default 1
             */
            draftVersion: number;
            /**
             * Draftdirty
             * @default true
             */
            draftDirty: boolean;
        };
        /** AgentSwarmRevisionResponseSchema */
        AgentSwarmRevisionResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * @description The ID of the organization this record belongs to.
             */
            organizationId?: string | null;
            /**
             * Swarmid
             * Format: uuid
             */
            swarmId: string;
            /** Revision */
            revision: number;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Description */
            description?: string | null;
            /** Availability */
            availability: string;
            /**
             * Publishedat
             * Format: date-time
             */
            publishedAt: string;
            /** Publishedby */
            publishedBy?: string | null;
            /** Revokedat */
            revokedAt?: string | null;
            /** Revokedby */
            revokedBy?: string | null;
            /** Revocationreason */
            revocationReason?: string | null;
            /** Cancellationrequestedat */
            cancellationRequestedAt?: string | null;
        };
        /** AgentSwarmRevokeRequestSchema */
        AgentSwarmRevokeRequestSchema: {
            /** Revision */
            revision: number;
            /** Reason */
            reason: string;
        };
        /** AgentSwarmUpdateRequestSchema */
        AgentSwarmUpdateRequestSchema: {
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** AgentToolInDb */
        AgentToolInDb: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Created At
             * Format: date-time
             * @description Record creation timestamp
             */
            created_at?: string;
            /**
             * Updated At
             * Format: date-time
             * @description Record last update timestamp
             */
            updated_at?: string;
            /**
             * Agent Id
             * Format: uuid
             * @description Agent ID for the tool.
             */
            agent_id: string;
            /**
             * Tool Id
             * Format: uuid
             * @description Tool ID for the agent.
             */
            tool_id: string;
            /**
             * Tool Revision
             * @description Exact tool revision.
             */
            tool_revision: number;
            /**
             * Organization Id
             * Format: uuid
             * @description Shared organization scope.
             */
            organization_id: string;
        };
        /** AgentToolRequest */
        AgentToolRequest: {
            /**
             * Toolid
             * Format: uuid
             */
            toolId: string;
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** AgentToolsResponseSchema */
        AgentToolsResponseSchema: {
            /** Items */
            items: components["schemas"]["ToolResponseSchema"][];
        };
        /** AgentUpdateRequestSchema */
        AgentUpdateRequestSchema: {
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Llmproviderconfigid */
            llmProviderConfigId?: string | null;
            /** Emailproviderconfigid */
            emailProviderConfigId?: string | null;
            /** Webrtcproviderconfigid */
            webrtcProviderConfigId?: string | null;
            /** Voiceconfigid */
            voiceConfigId?: string | null;
            llmOverrides?: components["schemas"]["LLMOverridesSchema"] | null;
            /** Rerankingproviderconfigid */
            rerankingProviderConfigId?: string | null;
            /** Memoryproviderconfigid */
            memoryProviderConfigId?: string | null;
            /**
             * Allowfileuploads
             * @default false
             */
            allowFileUploads: boolean;
            /** Fileuploadembeddingproviderconfigid */
            fileUploadEmbeddingProviderConfigId?: string | null;
            /** Instructiontemplateid */
            instructionTemplateId?: string | null;
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /**
         * AgentVoiceStackState
         * @enum {string}
         */
        AgentVoiceStackState: "not_published" | "text_only" | "decomposed" | "realtime";
        /**
         * AgentsPaginated
         * @description Paginated list of agents.
         */
        AgentsPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["AgentResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * AmbientNoiseConfig
         * @description Controls comfort noise played while the agent is thinking.
         */
        AmbientNoiseConfig: {
            /**
             * Enabled
             * @description Enable ambient comfort noise during agent thinking.
             * @default true
             */
            enabled: boolean;
            /**
             * Amplitude
             * @description Noise amplitude in int16 scale (0=silent, 50=subtle, 500=noticeable).
             * @default 50
             */
            amplitude: number;
        };
        /**
         * ApiKeyCreate
         * @description Schema for creating a new API Key.
         */
        ApiKeyCreate: {
            /**
             * Name
             * @description A label for the API Key.
             */
            name: string;
            /**
             * Isactive
             * @description Whether the key is active.
             * @default true
             */
            isActive: boolean;
            /**
             * Expiresat
             * @description Optional expiration date.
             */
            expiresAt?: string | null;
        };
        /**
         * ApiKeyInDb
         * @description Schema representing an API Key as stored in the database.
         */
        ApiKeyInDb: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Created At
             * Format: date-time
             * @description Record creation timestamp
             */
            created_at?: string;
            /**
             * Updated At
             * Format: date-time
             * @description Record last update timestamp
             */
            updated_at?: string;
            /**
             * Name
             * @description A label for the API Key.
             */
            name: string;
            /**
             * Is Active
             * @description Whether the key is active.
             * @default true
             */
            is_active: boolean;
            /**
             * Expires At
             * @description Optional expiration date.
             */
            expires_at?: string | null;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Key Prefix */
            key_prefix: string;
            /** Hashed Key */
            hashed_key: string;
            /** Last Used At */
            last_used_at?: string | null;
            /**
             * Usage Count
             * @default 0
             */
            usage_count: number;
        };
        /**
         * ApiKeyResponse
         * @description Schema for API Key responses. Includes the raw key only during creation.
         */
        ApiKeyResponse: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Name
             * @description A label for the API Key.
             */
            name: string;
            /**
             * Isactive
             * @description Whether the key is active.
             * @default true
             */
            isActive: boolean;
            /**
             * Expiresat
             * @description Optional expiration date.
             */
            expiresAt?: string | null;
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /** Keyprefix */
            keyPrefix: string;
            /** Hashedkey */
            hashedKey: string;
            /** Lastusedat */
            lastUsedAt?: string | null;
            /**
             * Usagecount
             * @default 0
             */
            usageCount: number;
            /**
             * Rawkey
             * @description The raw API key. Only returned once during creation.
             */
            rawKey?: string | null;
        };
        /** ArtifactPlan */
        ArtifactPlan: {
            /**
             * Transcript Storage Enabled
             * @default true
             */
            transcript_storage_enabled: boolean;
            /**
             * Audio Storage Enabled
             * @default false
             */
            audio_storage_enabled: boolean;
        };
        /**
         * AssistantMessageContent
         * @description Content structure for ASSISTANT messages in database.
         *
         *     Database format: {"role": "assistant", "content": [{"type": "text", ...}, ...]}
         */
        AssistantMessageContent: {
            /**
             * Role
             * @default assistant
             * @constant
             */
            role: "assistant";
            /**
             * Content
             * @description Assistant message blocks
             */
            content: (components["schemas"]["TextContent"] | components["schemas"]["ImageUrlContent"])[];
        };
        /**
         * AuthorizationRedirectSchema
         * @description Where to send the user to grant access.
         */
        AuthorizationRedirectSchema: {
            /** Authorizationurl */
            authorizationUrl: string;
            /**
             * Callbackorigin
             * @description Trusted origin that will post the OAuth completion message.
             */
            callbackOrigin: string;
            /** State */
            state: string;
        };
        /**
         * AvailableNumberSchema
         * @description A single available phone number from a provider search.
         */
        AvailableNumberSchema: {
            /** Phonenumber */
            phoneNumber: string;
            /** Friendlyname */
            friendlyName: string;
            /** Locality */
            locality?: string | null;
            /** Region */
            region?: string | null;
            /** Country */
            country?: string | null;
            /** Capabilities */
            capabilities?: {
                [key: string]: unknown;
            };
        };
        /**
         * AvailableNumbersResponseSchema
         * @description Response containing available numbers from a provider search.
         */
        AvailableNumbersResponseSchema: {
            /** Provider */
            provider: string;
            /** Country */
            country: string;
            /** Numbers */
            numbers: components["schemas"]["AvailableNumberSchema"][];
        };
        /** BackchannelConfig */
        BackchannelConfig: {
            /**
             * Enabled
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default false
             */
            enabled: boolean;
            /**
             * Frequency
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default 0.2
             */
            frequency: number;
            /**
             * Words
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            words?: string[];
        };
        /** BackgroundAudioConfig */
        BackgroundAudioConfig: {
            ambient_noise?: components["schemas"]["AmbientNoiseConfig"];
            filler?: components["schemas"]["FillerConfig"];
            /**
             * Denoising Mode
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default off
             * @enum {string}
             */
            denoising_mode: "off" | "noise-cancellation";
        };
        /**
         * BeginAuthorizationRequestSchema
         * @description Start an OAuth flow for an installed vendor.
         */
        BeginAuthorizationRequestSchema: {
            /**
             * Contactid
             * @description Bind the resulting connection to one end user.
             */
            contactId?: string | null;
        };
        /** CampaignAnalyticsResponse */
        CampaignAnalyticsResponse: {
            /**
             * Campaignid
             * Format: uuid
             */
            campaignId: string;
            /**
             * Totalcontacts
             * @default 0
             */
            totalContacts: number;
            /**
             * Completed
             * @default 0
             */
            completed: number;
            /**
             * Failed
             * @default 0
             */
            failed: number;
            /**
             * Pending
             * @default 0
             */
            pending: number;
            /**
             * Retry
             * @default 0
             */
            retry: number;
            /**
             * Skipped
             * @default 0
             */
            skipped: number;
            /**
             * Connectrate
             * @default 0
             */
            connectRate: number;
            /** Avgdurationseconds */
            avgDurationSeconds?: number | null;
            /**
             * Outcomedistribution
             * @default {}
             */
            outcomeDistribution: {
                [key: string]: number;
            };
        };
        /** CampaignContactResponse */
        CampaignContactResponse: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Campaignid
             * Format: uuid
             */
            campaignId: string;
            /** Campaignrevision */
            campaignRevision?: number | null;
            /** Contactid */
            contactId?: string | null;
            /** Contactaddress */
            contactAddress: string;
            /** Status */
            status: string;
            /**
             * Attemptcount
             * @default 0
             */
            attemptCount: number;
            /** Lastattemptat */
            lastAttemptAt?: string | null;
            /** Nextretryat */
            nextRetryAt?: string | null;
            /** Lasttrackingid */
            lastTrackingId?: string | null;
            /** Lastoutcomereason */
            lastOutcomeReason?: string | null;
            /**
             * Variables
             * @default {}
             */
            variables: {
                [key: string]: unknown;
            };
            /** Organizationid */
            organizationId?: string | null;
        };
        /** CampaignContactsPaginated */
        CampaignContactsPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["CampaignContactResponse"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * CampaignContactsSelectRequest
         * @description Select existing contacts by ID to add to a campaign.
         */
        CampaignContactsSelectRequest: {
            /** Contactids */
            contactIds: string[] | string;
        };
        /** CampaignContactsUploadRequest */
        CampaignContactsUploadRequest: {
            /** Contacts */
            contacts: components["schemas"]["ContactUploadRow"][];
        };
        /** CampaignCreateRequest */
        CampaignCreateRequest: {
            /** Name */
            name: string;
            /** Description */
            description?: string | null;
            /**
             * Channel
             * @default voice
             */
            channel: string;
            /** Channelconfig */
            channelConfig?: {
                [key: string]: unknown;
            };
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Initialmessagetemplateid */
            initialMessageTemplateId?: string | null;
            /** Scheduleconfig */
            scheduleConfig?: {
                [key: string]: unknown;
            } | null;
            /** Retrypolicy */
            retryPolicy?: {
                [key: string]: unknown;
            } | null;
            /**
             * Concurrencylimit
             * @default 5
             */
            concurrencyLimit: number;
        };
        /**
         * CampaignPreparationIssueCode
         * @description Stable UI-facing campaign preparation facts.
         * @enum {string}
         */
        CampaignPreparationIssueCode: "policy_not_evaluated" | "preferences_not_enforced" | "invalid_channel_address" | "contact_deletion_pending";
        /**
         * CampaignPreparationIssueLevel
         * @description Whether an issue is informational or prevents new work.
         * @enum {string}
         */
        CampaignPreparationIssueLevel: "warning" | "blocker";
        /** CampaignPreparationIssueResponse */
        CampaignPreparationIssueResponse: {
            code: components["schemas"]["CampaignPreparationIssueCode"];
            level: components["schemas"]["CampaignPreparationIssueLevel"];
            /** Affectedcontacts */
            affectedContacts: number;
            /** Message */
            message: string;
        };
        /** CampaignPreparationResponse */
        CampaignPreparationResponse: {
            /**
             * Campaignid
             * Format: uuid
             */
            campaignId: string;
            /** Selectedcontacts */
            selectedContacts: number;
            /** Warningfacts */
            warningFacts: number;
            /** Blockingfacts */
            blockingFacts: number;
            /** Issues */
            issues: components["schemas"]["CampaignPreparationIssueResponse"][];
        };
        /** CampaignResponse */
        CampaignResponse: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /** Name */
            name: string;
            /** Description */
            description?: string | null;
            /** Status */
            status: string;
            /**
             * Channel
             * @default voice
             */
            channel: string;
            /**
             * Channelconfig
             * @default {}
             */
            channelConfig: {
                [key: string]: unknown;
            };
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Agentrevision */
            agentRevision: number;
            /** Publishedrevision */
            publishedRevision: number;
            /** Activerevision */
            activeRevision?: number | null;
            /** Initialmessagetemplateid */
            initialMessageTemplateId?: string | null;
            /** Initialmessagetemplaterevision */
            initialMessageTemplateRevision?: number | null;
            /**
             * Scheduleconfig
             * @default {}
             */
            scheduleConfig: {
                [key: string]: unknown;
            };
            /**
             * Retrypolicy
             * @default {}
             */
            retryPolicy: {
                [key: string]: unknown;
            };
            /**
             * Concurrencylimit
             * @default 5
             */
            concurrencyLimit: number;
            /**
             * Totalcontacts
             * @default 0
             */
            totalContacts: number;
            /**
             * Completedcontacts
             * @default 0
             */
            completedContacts: number;
            /**
             * Failedcontacts
             * @default 0
             */
            failedContacts: number;
            /** Startedat */
            startedAt?: string | null;
            /** Completedat */
            completedAt?: string | null;
            /** Organizationid */
            organizationId?: string | null;
        };
        /** CampaignRevisionRevokeRequest */
        CampaignRevisionRevokeRequest: {
            /** Reason */
            reason: string;
        };
        /** CampaignUpdateRequest */
        CampaignUpdateRequest: {
            /** Expectedrevision */
            expectedRevision: number;
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Channel */
            channel?: string | null;
            /** Channelconfig */
            channelConfig?: {
                [key: string]: unknown;
            } | null;
            /** Agentid */
            agentId?: string | null;
            /** Initialmessagetemplateid */
            initialMessageTemplateId?: string | null;
            /** Scheduleconfig */
            scheduleConfig?: {
                [key: string]: unknown;
            } | null;
            /** Retrypolicy */
            retryPolicy?: {
                [key: string]: unknown;
            } | null;
            /** Concurrencylimit */
            concurrencyLimit?: number | null;
        };
        /** CampaignsPaginated */
        CampaignsPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["CampaignResponse"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /** CapabilitiesResponse */
        CapabilitiesResponse: {
            llm: components["schemas"]["CapabilityStatusResponse"];
            stt: components["schemas"]["CapabilityStatusResponse"];
            tts: components["schemas"]["CapabilityStatusResponse"];
            realtime: components["schemas"]["CapabilityStatusResponse"];
            webrtc: components["schemas"]["CapabilityStatusResponse"];
            telephony: components["schemas"]["CapabilityStatusResponse"];
            email: components["schemas"]["CapabilityStatusResponse"];
            storage: components["schemas"]["CapabilityStatusResponse"];
            memory: components["schemas"]["CapabilityStatusResponse"];
            embedding: components["schemas"]["CapabilityStatusResponse"];
            reranking: components["schemas"]["CapabilityStatusResponse"];
            sandbox: components["schemas"]["CapabilityStatusResponse"];
        };
        /**
         * Capability
         * @enum {string}
         */
        Capability: "llm" | "stt" | "tts" | "realtime" | "webrtc" | "telephony" | "email" | "storage" | "memory" | "embedding" | "reranking" | "sandbox";
        /** CapabilityDefinition */
        CapabilityDefinition: {
            capability: components["schemas"]["Capability"];
            /** Label */
            label: string;
            /** Description */
            description: string;
            /** Configure Via */
            configure_via: string;
            /** Providers */
            providers: components["schemas"]["ProviderDefinition"][];
        };
        /** CapabilityStatusResponse */
        CapabilityStatusResponse: {
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Providers */
            providers: string[];
        };
        /** CapabilityWarning */
        CapabilityWarning: {
            /** Section */
            section: string;
            /** Field */
            field: string;
            /** Message */
            message: string;
        };
        /** CompliancePlan */
        CompliancePlan: {
            /**
             * Recording Consent Required
             * @default true
             */
            recording_consent_required: boolean;
            /**
             * Recording Consent Message
             * @description Notification attempted before the greeting when recording_consent_required is set. Delivery state is visible, but notification failure or decline does not interrupt recording.
             * @default This call is recorded for quality and training purposes.
             */
            recording_consent_message: string;
            /**
             * Redact Pii In Transcripts
             * @default true
             */
            redact_pii_in_transcripts: boolean;
            /**
             * Redact Pii In Logs
             * @default true
             */
            redact_pii_in_logs: boolean;
            /**
             * Store Raw Vendor Payloads
             * @default false
             */
            store_raw_vendor_payloads: boolean;
            /**
             * Allow Sensitive Metadata
             * @default false
             */
            allow_sensitive_metadata: boolean;
        };
        /**
         * CompoundWidgetPayload
         * @description Validated compound widget payload — flat adjacency list of components.
         */
        CompoundWidgetPayload: {
            /**
             * Components
             * @description Flat list of component nodes
             */
            components: {
                [key: string]: unknown;
            }[];
            /**
             * Root
             * @description ID of the root component
             */
            root: string;
        };
        /**
         * ConnectCredentialRequestSchema
         * @description Direct credential entry, for vendors not using OAuth.
         */
        ConnectCredentialRequestSchema: {
            /**
             * Apikey
             * @description API key, for api_key vendors.
             */
            apiKey?: string | null;
            /**
             * Username
             * @description Username or account email, for basic vendors.
             */
            username?: string | null;
            /**
             * Password
             * @description Password or API token, for basic vendors.
             */
            password?: string | null;
            /**
             * Contactid
             * @description Bind to one end user. Omit for an organization-wide connection.
             */
            contactId?: string | null;
        };
        /**
         * ConnectionAggregateSchema
         * @description Connection plus its resolved organization or contact owner.
         */
        ConnectionAggregateSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Vendor */
            vendor: string;
            /** Displayname */
            displayName?: string | null;
            connectionKind: components["schemas"]["ConnectionKind"];
            status: components["schemas"]["ConnectionStatus"];
            /** Contactid */
            contactId?: string | null;
            /** Credentialsexpiresat */
            credentialsExpiresAt?: string | null;
            /** Createdat */
            createdAt?: string | null;
            /** Updatedat */
            updatedAt?: string | null;
            owner: components["schemas"]["ConnectionOwnerSummarySchema"];
        };
        /**
         * ConnectionKind
         * @description ConnectionKind behavior for the "mappers" domain.
         * @enum {string}
         */
        ConnectionKind: "ORGANIZATION" | "CONTACT";
        /**
         * ConnectionOwnerSummarySchema
         * @description Human-readable owner projection for an operator-facing connection list.
         */
        ConnectionOwnerSummarySchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["ConnectionKind"];
            /** Displayname */
            displayName: string;
        };
        /**
         * ConnectionSchema
         * @description A stored authorization. Credentials are never included.
         */
        ConnectionSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Vendor */
            vendor: string;
            /** Displayname */
            displayName?: string | null;
            connectionKind: components["schemas"]["ConnectionKind"];
            status: components["schemas"]["ConnectionStatus"];
            /** Contactid */
            contactId?: string | null;
            /** Credentialsexpiresat */
            credentialsExpiresAt?: string | null;
            /** Createdat */
            createdAt?: string | null;
            /** Updatedat */
            updatedAt?: string | null;
        };
        /**
         * ConnectionStatus
         * @description ConnectionStatus behavior for the "connections" domain.
         * @enum {string}
         */
        ConnectionStatus: "INITIATED" | "ACTIVE" | "INACTIVE" | "FAILED" | "REVOKED";
        /** ContactApiResponseSchema */
        ContactApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * @description The ID of the organization this record belongs to.
             */
            organizationId?: string | null;
            /** Name */
            name?: string | null;
            /** Primaryemail */
            primaryEmail?: string | null;
            /** Primaryphone */
            primaryPhone?: string | null;
            /** Preferences */
            preferences?: {
                [key: string]: string;
            } | null;
            lifecycle: components["schemas"]["ContactLifecycle"];
            /** Deletionrequestedat */
            deletionRequestedAt?: string | null;
        };
        /**
         * ContactCreateRequestSchema
         * @description Member-private contact creation payload.
         *
         *     The authenticated member owns the organization boundary. A caller cannot
         *     select it in the request body.
         */
        ContactCreateRequestSchema: {
            /** Externalid */
            externalId?: string | null;
            /** Name */
            name?: string | null;
            /** Primaryemail */
            primaryEmail?: string | null;
            /** Primaryphone */
            primaryPhone?: string | null;
            /** Preferences */
            preferences?: {
                [key: string]: string;
            } | null;
        };
        /**
         * ContactLifecycle
         * @description Whether a contact may enter new product work.
         * @enum {string}
         */
        ContactLifecycle: "active" | "deletion_pending";
        /**
         * ContactPatchRequestSchema
         * @description Patch only maintained contact fields; omission and null are distinct.
         */
        ContactPatchRequestSchema: {
            /** Externalid */
            externalId?: string | null;
            /** Name */
            name?: string | null;
            /** Primaryemail */
            primaryEmail?: string | null;
            /** Primaryphone */
            primaryPhone?: string | null;
            /** Preferences */
            preferences?: {
                [key: string]: string;
            } | null;
        };
        /**
         * ContactSortDirection
         * @enum {string}
         */
        ContactSortDirection: "asc" | "desc";
        /**
         * ContactSortField
         * @enum {string}
         */
        ContactSortField: "name" | "primary_email" | "primary_phone" | "created_at" | "updated_at";
        /**
         * ContactSummary
         * @description Lightweight contact representation for aggregates.
         */
        ContactSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name?: string | null;
            /** Primaryemail */
            primaryEmail?: string | null;
            /** Primaryphone */
            primaryPhone?: string | null;
        };
        /** ContactUploadRow */
        ContactUploadRow: {
            /** Contactaddress */
            contactAddress: string;
            /** Name */
            name?: string | null;
            /**
             * Variables
             * @default {}
             */
            variables: {
                [key: string]: unknown;
            };
        };
        /**
         * ContactsPaginated
         * @description Paginated list of Contact.
         */
        ContactsPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["ContactApiResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * ConversationAggregateBulkRequest
         * @description Request schema for bulk conversation aggregation.
         */
        ConversationAggregateBulkRequest: {
            /**
             * Conversationids
             * @description List of conversation IDs to aggregate
             */
            conversationIds: string[];
            /**
             * Includemessages
             * @description Include messages in response
             * @default true
             */
            includeMessages: boolean;
            /**
             * Messagelimit
             * @description Maximum number of messages per conversation
             * @default 50
             */
            messageLimit: number | null;
            /**
             * Includeparticipants
             * @description Include participants in response
             * @default true
             */
            includeParticipants: boolean;
        };
        /**
         * ConversationAggregateBulkResponse
         * @description Response schema for bulk conversation aggregation.
         */
        ConversationAggregateBulkResponse: {
            /** Conversations */
            conversations: components["schemas"]["ConversationAggregateResponse"][];
            /** Total */
            total: number;
        };
        /**
         * ConversationAggregateResponse
         * @description API response for a single aggregated conversation.
         *
         *     Exposed to frontend clients. Includes all related data in one response.
         *     Also used internally in service layer (replaces ConversationAggregateInDb).
         */
        ConversationAggregateResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /** Externalid */
            externalId?: string | null;
            channel: components["schemas"]["ConversationChannels"];
            status: components["schemas"]["ConversationStatus"];
            /** Title */
            title?: string | null;
            /**
             * Hastriggeredtitlegeneration
             * @default false
             */
            hasTriggeredTitleGeneration: boolean;
            /** Endedat */
            endedAt?: string | null;
            /** Swarmid */
            swarmId?: string | null;
            /** Swarmrevision */
            swarmRevision?: number | null;
            /** Meta */
            meta?: {
                [key: string]: unknown;
            } | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            contact?: components["schemas"]["ContactSummary"] | null;
            primaryAgent?: components["schemas"]["AgentSummary"] | null;
            /** Allagents */
            allAgents?: components["schemas"]["AgentSummary"][];
            /** Participants */
            participants?: components["schemas"]["ParticipantSummary"][];
            /** Messages */
            messages?: components["schemas"]["MessageSummary"][];
            /**
             * Messagecount
             * @default 0
             */
            messageCount: number;
            /**
             * Unreadcount
             * @default 0
             */
            unreadCount: number;
        };
        /** ConversationApiResponseSchema */
        ConversationApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /** @default CHAT */
            channel: components["schemas"]["ConversationChannels"];
            /** @default ACTIVE */
            status: components["schemas"]["ConversationStatus"];
            /** Title */
            title: string | null;
            /**
             * Hastriggeredtitlegeneration
             * @default false
             */
            hasTriggeredTitleGeneration: boolean | null;
            /** Endedat */
            endedAt?: string | null;
            /** Swarmid */
            swarmId?: string | null;
            /** Swarmrevision */
            swarmRevision?: number | null;
            /** Meta */
            meta?: {
                [key: string]: unknown;
            } | null;
        };
        /**
         * ConversationChannels
         * @description Enum for conversation channel types.
         *
         *     Identifies which interface initiated the conversation.
         *     Used to determine available tools and response formatting.
         * @enum {string}
         */
        ConversationChannels: "PHONE" | "CHAT" | "WEB" | "WIDGET" | "SMS" | "API";
        /**
         * ConversationControl
         * @description Top-level conversation behavior settings.
         */
        ConversationControl: {
            /**
             * First Message
             * @description Greeting text the agent speaks at the start of the session.
             */
            first_message?: string | null;
            /**
             * First Message Mode
             * @description Whether the agent speaks first or waits for the user.
             * @default assistant-speaks-first
             * @enum {string}
             */
            first_message_mode: "assistant-speaks-first" | "assistant-waits";
            /**
             * First Message Interruptible
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default false
             */
            first_message_interruptible: boolean;
            /**
             * Max Duration Seconds
             * @description Maximum call duration in seconds. 0 = unlimited.
             * @default 0
             */
            max_duration_seconds: number;
            /**
             * End Call Message
             * @description Message to play before ending the call (on timeout or end-call phrase).
             */
            end_call_message?: string | null;
            /**
             * End Call Phrases
             * @description Phrases that trigger call termination when spoken by the user.
             */
            end_call_phrases?: string[];
        };
        /**
         * ConversationMessagesPaginated
         * @description Paginated list of messages for a conversation.
         */
        ConversationMessagesPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["MessageApiResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * ConversationParticipantsPaginated
         * @description Paginated list of participants for a conversation.
         */
        ConversationParticipantsPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["ParticipantApiResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * ConversationSort
         * @enum {string}
         */
        ConversationSort: "title" | "created_at" | "updated_at" | "ended_at";
        /**
         * ConversationSortDirection
         * @enum {string}
         */
        ConversationSortDirection: "asc" | "desc";
        /**
         * ConversationStatus
         * @description Enum for conversation status.
         * @enum {string}
         */
        ConversationStatus: "ACTIVE" | "COMPLETED" | "ABANDONED";
        /**
         * ConversationsPaginated
         * @description Paginated list of conversations.
         */
        ConversationsPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["ConversationApiResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /** CorpusImportRead */
        CorpusImportRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Knowledgebase Id
             * Format: uuid
             */
            knowledgebase_id: string;
            state: components["schemas"]["DurableState"];
            /** Prefix */
            prefix: string;
            /**
             * Storage Provider Config Id
             * Format: uuid
             */
            storage_provider_config_id: string;
            /** Storage Provider Config Revision */
            storage_provider_config_revision: number;
            /** Storage Provider */
            storage_provider: string;
            /** Discovered Count */
            discovered_count: number;
            /** Queued Count */
            queued_count: number;
            /** Skipped */
            skipped: {
                [key: string]: unknown;
            } | null;
            /** Attempts */
            attempts: number;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Last Error */
            last_error: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * CorpusImportRequest
         * @description Sweeping a storage prefix into this knowledgebase.
         *
         *     No vendor field: the storage vendor is whatever the organization
         *     configured, the same one recordings use. A knowledgebase that could name
         *     its own storage would be a second place to configure credentials, and a
         *     second place for them to be wrong.
         */
        CorpusImportRequest: {
            /**
             * Storage Provider Config Id
             * Format: uuid
             * @description Explicit ready storage config whose current revision is pinned to the import and every child job.
             */
            storage_provider_config_id: string;
            /**
             * Prefix
             * @description Storage prefix to sweep, e.g. 'policies/'. Empty sweeps the whole root. Objects are matched by prefix, not by glob. Readable file types: .csv, .docx, .htm, .html, .json, .log, .markdown, .md, .pdf, .rst, .text, .tsv, .txt, .xhtml, .xls, .xlsm, .xlsx, .yaml, .yml. Anything else is skipped and reported on the import. Legacy .doc and .xls are different: .xls is read, .doc is not — it fails with a message asking for .docx, rather than being silently passed over.
             * @default
             */
            prefix: string;
        };
        /**
         * CuratedToolCatalogSchema
         * @description One curated tool as offered by the catalog, before any org installs it.
         */
        CuratedToolCatalogSchema: {
            /**
             * Wireid
             * @description Stable binding, e.g. linear.list_issues.
             */
            wireId: string;
            /**
             * Name
             * @description Vendor-scoped tool name, and the path segment used to address this tool, e.g. list_issues.
             */
            name: string;
            /**
             * Agentname
             * @description Fully qualified name an agent sees, e.g. linear_list_issues.
             */
            agentName: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description: string;
            /** @description Whether the tool may change vendor-side state. */
            effect: components["schemas"]["ToolEffect"];
            /**
             * Scopes
             * @description Provider-native scopes this tool needs.
             */
            scopes?: string[];
        };
        /**
         * CuratedVendorDetailSchema
         * @description One curated vendor with the tools it offers.
         */
        CuratedVendorDetailSchema: {
            /** Vendor */
            vendor: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description: string;
            /** Categories */
            categories?: string[];
            /** Authkinds */
            authKinds?: components["schemas"]["VendorAuthKind"][];
            /** Homepageurl */
            homepageUrl?: string | null;
            /**
             * Requiresinstanceurl
             * @description Whether installing requires a customer-owned origin.
             * @default false
             */
            requiresInstanceUrl: boolean;
            /** Instanceurllabel */
            instanceUrlLabel?: string | null;
            /** Instanceurlplaceholder */
            instanceUrlPlaceholder?: string | null;
            /**
             * Requiresoauthapp
             * @description Whether installing requires your own OAuth client id and secret.
             * @default false
             */
            requiresOauthApp: boolean;
            /**
             * Requiresoauthtenant
             * @description Whether the provider's endpoints are per-tenant.
             * @default false
             */
            requiresOauthTenant: boolean;
            /**
             * Toolcount
             * @description Curated tools this deployment carries.
             */
            toolCount: number;
            /**
             * Installed
             * @description Whether this organization installed it.
             */
            installed: boolean;
            /** Tools */
            tools?: components["schemas"]["CuratedToolCatalogSchema"][];
        };
        /**
         * CuratedVendorSummarySchema
         * @description One curated vendor in the browse list.
         */
        CuratedVendorSummarySchema: {
            /** Vendor */
            vendor: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description: string;
            /** Categories */
            categories?: string[];
            /** Authkinds */
            authKinds?: components["schemas"]["VendorAuthKind"][];
            /** Homepageurl */
            homepageUrl?: string | null;
            /**
             * Requiresinstanceurl
             * @description Whether installing requires a customer-owned origin.
             * @default false
             */
            requiresInstanceUrl: boolean;
            /** Instanceurllabel */
            instanceUrlLabel?: string | null;
            /** Instanceurlplaceholder */
            instanceUrlPlaceholder?: string | null;
            /**
             * Requiresoauthapp
             * @description Whether installing requires your own OAuth client id and secret.
             * @default false
             */
            requiresOauthApp: boolean;
            /**
             * Requiresoauthtenant
             * @description Whether the provider's endpoints are per-tenant.
             * @default false
             */
            requiresOauthTenant: boolean;
            /**
             * Toolcount
             * @description Curated tools this deployment carries.
             */
            toolCount: number;
            /**
             * Installed
             * @description Whether this organization installed it.
             */
            installed: boolean;
        };
        /**
         * DefinitionLifecycle
         * @description Lifecycle of a stable definition header and its published alias.
         * @enum {string}
         */
        DefinitionLifecycle: "draft" | "published" | "withdrawn" | "archived";
        /**
         * DeletionErrorCode
         * @description Bounded diagnostics that cannot contain product or provider data.
         * @enum {string}
         */
        DeletionErrorCode: "call_active" | "object_delete_failed" | "erasure_failed" | "dependency_unavailable" | "internal_failure";
        /**
         * DeletionJobApiResponse
         * @description An asynchronous deletion monitor; it makes no provider-side claim.
         */
        DeletionJobApiResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            targetType: components["schemas"]["DeletionTargetType"];
            /**
             * Targetid
             * Format: uuid
             */
            targetId: string;
            /**
             * Requestedbymemberid
             * Format: uuid
             */
            requestedByMemberId: string;
            status: components["schemas"]["DeletionJobStatus"];
            errorCode: components["schemas"]["DeletionErrorCode"] | null;
            /**
             * Requestedat
             * Format: date-time
             */
            requestedAt: string;
            /** Startedat */
            startedAt: string | null;
            /** Finishedat */
            finishedAt: string | null;
            /** Statusurl */
            statusUrl: string;
            /** Message */
            message: string;
        };
        /**
         * DeletionJobStatus
         * @description Organization-visible product state, separate from Absurd claims.
         * @enum {string}
         */
        DeletionJobStatus: "pending" | "running" | "succeeded" | "failed";
        /**
         * DeletionTargetType
         * @description Lifecycle roots organizations may erase from Eylo in V1.
         * @enum {string}
         */
        DeletionTargetType: "call" | "contact";
        /** DurableConsumerHealthResponse */
        DurableConsumerHealthResponse: {
            /** Consumer Name */
            consumer_name: string;
            /** Event Type */
            event_type: string;
            /** Event Version */
            event_version: number;
        };
        /** DurableDeliveryHealthResponse */
        DurableDeliveryHealthResponse: {
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Total Count */
            total_count: number;
            /** Pending Count */
            pending_count: number;
            /** Running Count */
            running_count: number;
            /** Succeeded Count */
            succeeded_count: number;
            /** Dead Letter Count */
            dead_letter_count: number;
            /** Oldest Pending Age Seconds */
            oldest_pending_age_seconds: number | null;
            /** Unsupported Delivery Count */
            unsupported_delivery_count: number;
            /** Registered Consumers */
            registered_consumers: components["schemas"]["DurableConsumerHealthResponse"][];
            /** Unsupported Consumers */
            unsupported_consumers: components["schemas"]["UnsupportedConsumerHealthResponse"][];
        };
        /**
         * DurableState
         * @enum {string}
         */
        DurableState: "pending" | "running" | "succeeded" | "failed" | "cancelled";
        /** EmailConfigCreate */
        EmailConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** EmailConfigResponse */
        EmailConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** EmailConfigUpdate */
        EmailConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** EmailConfigVerificationResponse */
        EmailConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /** EmbeddingConfigCreate */
        EmbeddingConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** EmbeddingConfigResponse */
        EmbeddingConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Dimensions */
            dimensions: number | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** EmbeddingConfigUpdate */
        EmbeddingConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** EmbeddingConfigVerificationResponse */
        EmbeddingConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /** Dimensions */
            dimensions: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /** EventHealthResponse */
        EventHealthResponse: {
            durable: components["schemas"]["DurableDeliveryHealthResponse"];
            local: components["schemas"]["LocalListenerHealthResponse"];
        };
        /**
         * ExecutionBudgetDimension
         * @description The exact organization execution boundary that rejected a run.
         * @enum {string}
         */
        ExecutionBudgetDimension: "concurrency" | "tokens" | "active_time" | "cost";
        /** FallbackChainsConfig */
        FallbackChainsConfig: {
            /**
             * Stt Enabled
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default false
             */
            stt_enabled: boolean;
            /**
             * Tts Enabled
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default false
             */
            tts_enabled: boolean;
            /**
             * Realtime Enabled
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default false
             */
            realtime_enabled: boolean;
        };
        /**
         * FillerConfig
         * @description Controls filler phrase injection during LLM thinking gaps.
         */
        FillerConfig: {
            /**
             * Enabled
             * @description Enable filler phrase injection.
             * @default true
             */
            enabled: boolean;
            /**
             * Phrases
             * @description Filler phrases to randomly choose from.
             */
            phrases?: string[];
            /**
             * Delay Ms
             * @description Milliseconds to wait before injecting a filler phrase.
             * @default 3000
             */
            delay_ms: number;
        };
        /**
         * ForgotPasswordRequestSchema
         * @description Request schema for initiating a password reset.
         */
        ForgotPasswordRequestSchema: {
            /**
             * Email
             * Format: email
             * @description Member email address
             */
            email: string;
        };
        /**
         * GrantCreate
         * @description Granting an agent access to a knowledgebase.
         *
         *     `access` defaults to READ. An unspecified grant is a read grant — the
         *     caller has to say `READ_WRITE` to get it, so write access is always
         *     something someone chose.
         */
        GrantCreate: {
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /**
             * Knowledgebase Id
             * Format: uuid
             */
            knowledgebase_id: string;
            /** @default read */
            access: components["schemas"]["KnowledgeAccess"];
        };
        /**
         * GrantCuratedToolRequestSchema
         * @description Optimistic-concurrency guard for changing an Agent draft grant.
         */
        GrantCuratedToolRequestSchema: {
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** GrantRead */
        GrantRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /**
             * Knowledgebase Id
             * Format: uuid
             */
            knowledgebase_id: string;
            access: components["schemas"]["KnowledgeAccess"];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HookConfig */
        HookConfig: {
            /**
             * Name
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            name: string;
            /**
             * Enabled
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default true
             */
            enabled: boolean;
            /**
             * Event
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            event: string;
            /**
             * Url
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            url?: string | null;
            /**
             * Headers
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            headers?: {
                [key: string]: string;
            };
        };
        /**
         * ImageUrlContent
         * @description Image URL content block in a message.
         */
        ImageUrlContent: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "image_url";
            /** @description Image URL payload */
            image_url: components["schemas"]["ImageUrlPayload"];
        };
        /**
         * ImageUrlPayload
         * @description URL payload for an image content block.
         */
        ImageUrlPayload: {
            /**
             * Url
             * @description HTTP(S) URL for the image
             */
            url: string;
            /**
             * Mime Type
             * @description Concrete image MIME type, for vendors that require it
             */
            mime_type?: string | null;
        };
        /**
         * IngestRequest
         * @description Submitting a document for ingestion.
         *
         *     `scope` and `scope_id` are not here. A document belongs to the
         *     knowledgebase it is ingested into, and that knowledgebase already has a
         *     scope — accepting one here would let a caller file an agent-scoped document
         *     into an organization-wide knowledgebase, where every agent would then read
         *     it.
         */
        IngestRequest: {
            /** Content */
            content: string;
            /** Title */
            title?: string | null;
            /**
             * Source Uri
             * @description A durable address for this document. When set, it becomes the document's identity, so re-ingesting the same URI replaces the previous version instead of adding a second copy. Without it, identity falls back to the content itself and an edited document becomes a new one.
             */
            source_uri?: string | null;
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            } | null;
        };
        /** IngestionJobRead */
        IngestionJobRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Knowledgebase Id
             * Format: uuid
             */
            knowledgebase_id: string;
            state: components["schemas"]["DurableState"];
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Document Key */
            document_key: string;
            /** Title */
            title: string | null;
            /** Source Uri */
            source_uri: string | null;
            /** Storage Key */
            storage_key: string | null;
            /** Storage Provider Config Id */
            storage_provider_config_id: string | null;
            /** Storage Provider Config Revision */
            storage_provider_config_revision: number | null;
            /** Storage Provider */
            storage_provider: string | null;
            /** Embedding Provider Config Id */
            embedding_provider_config_id: string | null;
            /** Embedding Provider Config Revision */
            embedding_provider_config_revision: number | null;
            /** Embedding Provider */
            embedding_provider: string | null;
            /** Embedding Model */
            embedding_model: string | null;
            /** Embedding Dimensions */
            embedding_dimensions: number | null;
            /** Embedding Semantic Options */
            embedding_semantic_options: {
                [key: string]: unknown;
            } | null;
            /** Embedding Space Id */
            embedding_space_id: string | null;
            /** Corpus Import Id */
            corpus_import_id: string | null;
            /** Attempts */
            attempts: number;
            /** Max Attempts */
            max_attempts: number;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Last Error */
            last_error: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * InitiatingPrincipalKind
         * @description Durable authority kinds that may initiate agent work.
         * @enum {string}
         */
        InitiatingPrincipalKind: "member" | "contact" | "api_key" | "widget" | "worker";
        /**
         * InstallVendorRequestSchema
         * @description Install one curated vendor for the authenticated organization.
         */
        InstallVendorRequestSchema: {
            /** @description Which of the vendor's supported auth modes to use. */
            authKind: components["schemas"]["VendorAuthKind"];
            /**
             * Instanceurl
             * @description Customer-owned HTTPS origin, for vendors that require one.
             */
            instanceUrl?: string | null;
            /**
             * Oauthclientid
             * @description Client id of your own OAuth app for this vendor.
             */
            oauthClientId?: string | null;
            /**
             * Oauthclientsecret
             * @description Client secret of your own OAuth app. Stored encrypted.
             */
            oauthClientSecret?: string | null;
            /**
             * Oauthtenant
             * @description Directory id, for per-tenant providers such as Microsoft.
             */
            oauthTenant?: string | null;
        };
        /**
         * InstallationSchema
         * @description One organization's installation of a curated vendor.
         */
        InstallationSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Vendor */
            vendor: string;
            /** Displayname */
            displayName: string;
            authKind: components["schemas"]["VendorAuthKind"];
            /** Instanceurl */
            instanceUrl?: string | null;
            /** Oauthclientid */
            oauthClientId?: string | null;
            /** Oauthtenant */
            oauthTenant?: string | null;
            /**
             * Installedat
             * Format: date-time
             */
            installedAt: string;
            /**
             * Installedby
             * Format: uuid
             */
            installedBy: string;
        };
        /**
         * InstalledToolSchema
         * @description One curated tool an organization has materialized, with its policy.
         */
        InstalledToolSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Wireid */
            wireId: string;
            /**
             * Name
             * @description Path segment used to address this tool.
             */
            name: string;
            /**
             * Agentname
             * @description Fully qualified name an agent sees.
             */
            agentName: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description: string;
            effect: components["schemas"]["ToolEffect"];
            executionMode: components["schemas"]["eylo__modules__integrations_v2__domain__enums__ToolExecutionMode"];
        };
        /**
         * InterruptionType
         * @enum {string}
         */
        InterruptionType: "transcript" | "vad";
        /**
         * InviteMemberRequestSchema
         * @description Request schema for inviting a member to an organization.
         */
        InviteMemberRequestSchema: {
            /**
             * Email
             * Format: email
             * @description Invitee email address
             */
            email: string;
        };
        JsonValue: unknown;
        /**
         * KeypadInputPlan
         * @description Per-agent keypad behaviour.
         */
        KeypadInputPlan: {
            /**
             * Enabled
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default false
             */
            enabled: boolean;
            /**
             * Digit Limit
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default 6
             */
            digit_limit: number;
            /**
             * Termination Key
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default #
             */
            termination_key: string;
            /**
             * Timeout Ms
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default 5000
             */
            timeout_ms: number;
        };
        /**
         * KnowledgeAccess
         * @description What a grant permits. A property of the grant, not of the agent.
         * @enum {string}
         */
        KnowledgeAccess: "read" | "read_write";
        /**
         * KnowledgeChunkingStrategy
         * @description Stable strategy names shared by config validation and chunking adapters.
         * @enum {string}
         */
        KnowledgeChunkingStrategy: "fixed" | "markdown" | "paragraph";
        /** KnowledgeEmbeddingSpaceRead */
        KnowledgeEmbeddingSpaceRead: {
            /**
             * Provider Config Id
             * Format: uuid
             */
            provider_config_id: string;
            /** Provider Config Revision */
            provider_config_revision: number;
            /** Provider */
            provider: string;
            /** Model */
            model: string;
            /** Dimensions */
            dimensions: number;
            /** Space Id */
            space_id: string;
        };
        /** KnowledgeReindexJobRead */
        KnowledgeReindexJobRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Knowledgebase Id
             * Format: uuid
             */
            knowledgebase_id: string;
            state: components["schemas"]["DurableState"];
            /** Source Embedding Space Id */
            source_embedding_space_id: string;
            /**
             * Target Embedding Provider Config Id
             * Format: uuid
             */
            target_embedding_provider_config_id: string;
            /** Target Embedding Provider Config Revision */
            target_embedding_provider_config_revision: number;
            /** Target Embedding Provider */
            target_embedding_provider: string;
            /** Target Embedding Model */
            target_embedding_model: string;
            /** Target Embedding Dimensions */
            target_embedding_dimensions: number;
            /** Target Embedding Semantic Options */
            target_embedding_semantic_options: {
                [key: string]: unknown;
            };
            /** Target Embedding Space Id */
            target_embedding_space_id: string;
            /** Source Chunk Count */
            source_chunk_count: number;
            /** Indexed Chunk Count */
            indexed_chunk_count: number;
            /** Attempts */
            attempts: number;
            /** Max Attempts */
            max_attempts: number;
            /** Last Error */
            last_error: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * KnowledgeReindexState
         * @description Operator-visible state of one pgvector space transition.
         * @enum {string}
         */
        KnowledgeReindexState: "active" | "reindex_required" | "reindexing" | "failed";
        /**
         * KnowledgeReindexStatusRead
         * @description Current, staged, and available vector authority for one knowledgebase.
         */
        KnowledgeReindexStatusRead: {
            state: components["schemas"]["KnowledgeReindexState"];
            active_space: components["schemas"]["KnowledgeEmbeddingSpaceRead"];
            target_space: components["schemas"]["KnowledgeEmbeddingSpaceRead"] | null;
            available_space: components["schemas"]["KnowledgeEmbeddingSpaceRead"] | null;
            /** Update Available */
            update_available: boolean;
            /** Last Error */
            last_error: string | null;
            latest_job: components["schemas"]["KnowledgeReindexJobRead"] | null;
        };
        /**
         * KnowledgeScope
         * @description Who a document belongs to.
         * @enum {string}
         */
        KnowledgeScope: "organization" | "agent" | "conversation";
        /**
         * KnowledgebaseCreate
         * @description Creating a knowledgebase.
         *
         *     `vendor` has no default. Choosing one on the operator's behalf would decide
         *     what "similar" means for every future query — a Postgres FTS KB and a
         *     pgvector KB answer the same question differently, and neither is the
         *     obvious right answer.
         */
        KnowledgebaseCreate: {
            /** Name */
            name: string;
            /** Vendor */
            vendor: string;
            scope: components["schemas"]["KnowledgeScope"];
            /** Scope Id */
            scope_id: string;
            /**
             * Writable
             * @description Whether this knowledgebase accepts writes at all. A grant cannot exceed it, so an imported source stays read-only however it is granted.
             * @default false
             */
            writable: boolean;
            /**
             * Embedding Provider Config Id
             * @description Required for pgvector and rejected for vendors that do not embed. The selected ready revision becomes this knowledgebase's immutable vector space.
             */
            embedding_provider_config_id?: string | null;
            metadata?: components["schemas"]["KnowledgebaseMetadata"] | null;
        };
        /**
         * KnowledgebaseMetadata
         * @description Complete, executable knowledgebase behavior configuration.
         */
        KnowledgebaseMetadata: {
            /** @default paragraph */
            chunking: components["schemas"]["KnowledgeChunkingStrategy"];
            /**
             * Chunk Size
             * @default 1200
             */
            chunk_size: number;
            /**
             * Chunk Overlap
             * @default 150
             */
            chunk_overlap: number;
        };
        /** KnowledgebaseRead */
        KnowledgebaseRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Vendor */
            vendor: string;
            scope: components["schemas"]["KnowledgeScope"];
            /** Scope Id */
            scope_id: string;
            /** Writable */
            writable: boolean;
            /** Embedding Provider Config Id */
            embedding_provider_config_id: string | null;
            /** Embedding Provider Config Revision */
            embedding_provider_config_revision: number | null;
            /** Embedding Provider */
            embedding_provider: string | null;
            /** Embedding Endpoint */
            embedding_endpoint: string | null;
            /** Embedding Model */
            embedding_model: string | null;
            /** Embedding Dimensions */
            embedding_dimensions: number | null;
            /** Embedding Semantic Options */
            embedding_semantic_options: {
                [key: string]: unknown;
            } | null;
            /** Embedding Space Id */
            embedding_space_id: string | null;
            reindex_state: components["schemas"]["KnowledgeReindexState"];
            /** Target Embedding Provider Config Id */
            target_embedding_provider_config_id: string | null;
            /** Target Embedding Provider Config Revision */
            target_embedding_provider_config_revision: number | null;
            /** Target Embedding Provider */
            target_embedding_provider: string | null;
            /** Target Embedding Endpoint */
            target_embedding_endpoint: string | null;
            /** Target Embedding Model */
            target_embedding_model: string | null;
            /** Target Embedding Dimensions */
            target_embedding_dimensions: number | null;
            /** Target Embedding Semantic Options */
            target_embedding_semantic_options: {
                [key: string]: unknown;
            } | null;
            /** Target Embedding Space Id */
            target_embedding_space_id: string | null;
            /** Reindex Last Error */
            reindex_last_error: string | null;
            metadata: components["schemas"]["KnowledgebaseMetadata"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** KnowledgebaseReindexRequest */
        KnowledgebaseReindexRequest: {
            /**
             * Embedding Provider Config Id
             * Format: uuid
             */
            embedding_provider_config_id: string;
        };
        /** KnowledgebaseUpdate */
        KnowledgebaseUpdate: {
            /** Name */
            name?: string | null;
            /** Writable */
            writable?: boolean | null;
            metadata?: components["schemas"]["KnowledgebaseMetadata"] | null;
        };
        /** LLMConfigCreate */
        LLMConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** LLMConfigResponse */
        LLMConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** LLMConfigUpdate */
        LLMConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** LLMConfigVerificationResponse */
        LLMConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Model */
            model: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /**
         * LLMModels
         * @enum {string}
         */
        LLMModels: "claude-sonnet-4-5-20250929" | "claude-haiku-4-5-20251001" | "claude-opus-4-5-20251101" | "claude-opus-4-1-20250805" | "claude-sonnet-4-20250514" | "claude-3-7-sonnet-20250219" | "claude-opus-4-20250514" | "claude-3-haiku-20240307" | "claude-3-5-sonnet-20241022" | "global.anthropic.claude-sonnet-4-5-20250929-v1:0" | "global.anthropic.claude-opus-4-5-20251101-v1:0" | "global.anthropic.claude-haiku-4-5-20251001-v1:0" | "global.anthropic.claude-sonnet-4-20250514-v1:0" | "apac.anthropic.claude-sonnet-4-20250514-v1:0" | "apac.anthropic.claude-3-7-sonnet-20250219-v1:0" | "apac.anthropic.claude-3-5-sonnet-20241022-v2:0" | "apac.anthropic.claude-3-5-sonnet-20240620-v1:0" | "apac.anthropic.claude-3-sonnet-20240229-v1:0" | "apac.anthropic.claude-3-haiku-20240307-v1:0" | "anthropic.claude-3-7-sonnet-20250219-v1:0" | "us.anthropic.claude-3-7-sonnet-20250219-v1:0" | "eu.anthropic.claude-3-7-sonnet-20250219-v1:0" | "anthropic.claude-3-5-sonnet-20241022-v2:0" | "us.anthropic.claude-3-5-sonnet-20241022-v2:0" | "anthropic.claude-3-5-sonnet-20240620-v1:0" | "us.anthropic.claude-3-5-sonnet-20240620-v1:0" | "eu.anthropic.claude-3-5-sonnet-20240620-v1:0" | "us.anthropic.claude-3-5-haiku-20241022-v1:0" | "us.anthropic.claude-3-sonnet-20240229-v1:0" | "eu.anthropic.claude-3-sonnet-20240229-v1:0" | "anthropic.claude-3-haiku-20240307-v1:0" | "us.anthropic.claude-3-haiku-20240307-v1:0" | "eu.anthropic.claude-3-haiku-20240307-v1:0" | "us.anthropic.claude-3-opus-20240229-v1:0" | "anthropic.claude-sonnet-4-20250514-v1:0" | "us.anthropic.claude-sonnet-4-20250514-v1:0" | "eu.anthropic.claude-sonnet-4-20250514-v1:0" | "anthropic.claude-sonnet-4-5-20250929-v1:0" | "us.anthropic.claude-sonnet-4-5-20250929-v1:0" | "au.anthropic.claude-sonnet-4-5-20250929-v1:0" | "eu.anthropic.claude-sonnet-4-5-20250929-v1:0" | "jp.anthropic.claude-sonnet-4-5-20250929-v1:0" | "us.anthropic.claude-opus-4-20250514-v1:0" | "anthropic.claude-opus-4-1-20250805-v1:0" | "us.anthropic.claude-opus-4-1-20250805-v1:0" | "us.anthropic.claude-opus-4-5-20251101-v1:0" | "eu.anthropic.claude-opus-4-5-20251101-v1:0" | "us.anthropic.claude-haiku-4-5-20251001-v1:0" | "au.anthropic.claude-haiku-4-5-20251001-v1:0" | "eu.anthropic.claude-haiku-4-5-20251001-v1:0" | "jp.anthropic.claude-haiku-4-5-20251001-v1:0" | "gemini-2.0-flash-exp" | "gemini-2.0-flash-001" | "gemini-1.5-pro" | "gemini-1.5-flash" | "gemini-3-flash-preview" | "gemini-3-pro-preview" | "gemini-2.5-flash" | "gemini-2.5-pro" | "gemini-2.5-flash-lite" | "gpt-5.4" | "gpt-5.4-pro" | "gpt-5.4-mini" | "gpt-5.4-nano" | "gpt-5-mini" | "gpt-5-nano" | "gpt-5" | "gpt-4.1" | "gpt-4o" | "gpt-4o-mini" | "gpt-4-turbo" | "gpt-4" | "gpt-3.5-turbo" | "gpt-5.2" | "gpt-5.1" | "gpt-5.2-pro" | "gpt-5-pro" | "sarvam-30b" | "sarvam-105b" | "sarvam-m" | "llama3.1-8b" | "gpt-oss-120b" | "qwen-3-235b-a22b-instruct-2507" | "zai-glm-4.7" | "llama-3.1-8b-instant" | "llama-3.3-70b-versatile" | "openai/gpt-oss-120b" | "openai/gpt-oss-20b" | "moonshotai/kimi-k2-instruct-0905" | "qwen/qwen3-32b";
        /**
         * LLMOverridesSchema
         * @description Optional non-secret generation overrides stored on an agent.
         */
        LLMOverridesSchema: {
            model?: components["schemas"]["LLMModels"] | null;
            /** Maxtokens */
            maxTokens?: number | null;
            /** Temperature */
            temperature?: number | null;
            /** Topk */
            topK?: number | null;
            /** Topp */
            topP?: number | null;
            /** Stopsequences */
            stopSequences?: string[] | null;
        };
        /** LocalListenerHealthResponse */
        LocalListenerHealthResponse: {
            /** Manifest Version */
            manifest_version: number;
            /** Process Role */
            process_role: string;
            /** Delivery Class */
            delivery_class: string;
            /** Healthy */
            healthy: boolean;
            /** Handler Count */
            handler_count: number;
            /** Event Count */
            event_count: number;
            /** Handler Ids */
            handler_ids: string[];
        };
        /**
         * LoginRequestSchema
         * @description Schema for user login request.
         */
        LoginRequestSchema: {
            /**
             * Email
             * Format: email
             * @description Member's email address
             */
            email: string;
            /**
             * Password
             * @description Member's password
             */
            password: string;
        };
        /** MCPServerCreate */
        MCPServerCreate: {
            /** Name */
            name: string;
            /**
             * Url
             * @description Streamable HTTP endpoint. stdio is not supported.
             */
            url: string;
            /**
             * Headers
             * @description Sent on every request — this is where a bearer token goes. Values are never returned.
             */
            headers?: {
                [key: string]: string;
            };
        };
        /** MCPServerPatch */
        MCPServerPatch: {
            /** Expected Draft Version */
            expected_draft_version: number;
            /** Name */
            name?: string | null;
            /** Url */
            url?: string | null;
            /**
             * Headers
             * @description Secret patch: omitted keys stay unchanged; string replaces; null removes.
             */
            headers?: {
                [key: string]: string | null;
            } | null;
        };
        /** MCPServerRevoke */
        MCPServerRevoke: {
            /** Reason */
            reason: string;
        };
        /** MemberApiResponseSchema */
        MemberApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Member ID
             */
            id: string;
            /**
             * Organizationid
             * Format: uuid
             * @description Organization ID
             */
            organizationId: string;
            /**
             * Email
             * Format: email
             * @description User's email address
             */
            email: string;
            /**
             * Name
             * @description User's full name
             */
            name: string;
            /**
             * @description User's status in the organization
             * @default ACTIVE
             */
            status: components["schemas"]["MemberStatus"];
            /**
             * Lastlogin
             * @description Last login timestamp
             */
            lastLogin?: string | null;
            /**
             * Createdat
             * Format: date-time
             * @description Timestamp when the user was created
             */
            createdAt: string;
        };
        /**
         * MemberSortDirection
         * @enum {string}
         */
        MemberSortDirection: "asc" | "desc";
        /**
         * MemberSortField
         * @enum {string}
         */
        MemberSortField: "name" | "email" | "status" | "last_login" | "created_at";
        /**
         * MemberStatus
         * @description Enum for org member status
         * @enum {string}
         */
        MemberStatus: "ACTIVE" | "INACTIVE" | "WAITLIST";
        /**
         * MembersPaginated
         * @description Paginated list of members.
         */
        MembersPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["MemberApiResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * MemoryActor
         * @description The exact principal responsible for a deliberate memory action.
         */
        MemoryActor: {
            kind: components["schemas"]["MemoryActorKind"];
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Agent Id */
            agent_id?: string | null;
            /** Agent Revision */
            agent_revision?: number | null;
        };
        /**
         * MemoryActorKind
         * @description Organization-authorized principals that can deliberately change memory.
         * @enum {string}
         */
        MemoryActorKind: "agent_participant" | "organization_member";
        /** MemoryChangeRead */
        MemoryChangeRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            event: components["schemas"]["MemoryEvent"];
            /** Before */
            before: string | null;
            /** After */
            after: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Source Conversation Id */
            source_conversation_id: string | null;
            provenance: components["schemas"]["MemoryProvenance"];
        };
        /** MemoryConfigCreate */
        MemoryConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** MemoryConfigResponse */
        MemoryConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** MemoryConfigUpdate */
        MemoryConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** MemoryConfigVerificationResponse */
        MemoryConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /** MemoryDetailRead */
        MemoryDetailRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Content */
            content: string;
            level: components["schemas"]["MemoryLevel"];
            /**
             * Subject Id
             * Format: uuid
             */
            subject_id: string;
            /** Subject Label */
            subject_label: string;
            status: components["schemas"]["MemoryStatus"];
            integrity: components["schemas"]["MemoryIntegrityState"];
            /**
             * Source Conversation Id
             * Format: uuid
             */
            source_conversation_id: string;
            /** Recall Count */
            recall_count: number;
            /** Last Recalled At */
            last_recalled_at: string | null;
            /** Expires At */
            expires_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            };
            provenance: components["schemas"]["MemoryProvenance"];
            /** History */
            history: components["schemas"]["MemoryChangeRead"][];
            /** Relationships */
            relationships: components["schemas"]["MemoryRelationshipRead"][];
            latest_reconciliation: components["schemas"]["MemoryReconciliationJobRead"] | null;
        };
        /** MemoryEmbeddingSpaceRead */
        MemoryEmbeddingSpaceRead: {
            /**
             * Provider Config Id
             * Format: uuid
             */
            provider_config_id: string;
            /** Provider Config Revision */
            provider_config_revision: number;
            /** Provider */
            provider: string;
            /** Model */
            model: string;
            /** Dimensions */
            dimensions: number;
            /** Space Id */
            space_id: string;
        };
        /**
         * MemoryEvent
         * @description What happened to a memory. mem0's vocabulary, and the history's.
         * @enum {string}
         */
        MemoryEvent: "add" | "update" | "expire" | "delete" | "noop";
        /**
         * MemoryExtractionAuthority
         * @description Exact configured model and prompt authority used to infer a transition.
         */
        MemoryExtractionAuthority: {
            /**
             * Provider Config Id
             * Format: uuid
             */
            provider_config_id: string;
            /** Provider Config Revision */
            provider_config_revision: number;
            /** Provider */
            provider: string;
            /** Model */
            model: string;
            /** Prompt Revision */
            prompt_revision: string;
        };
        /**
         * MemoryIntegrityState
         * @enum {string}
         */
        MemoryIntegrityState: "checking" | "conflicted" | "consolidated" | "healthy";
        /**
         * MemoryLevel
         * @description The product subject that owns one remembered fact.
         * @enum {string}
         */
        MemoryLevel: "agent" | "user" | "conversation";
        /** MemoryListRead */
        MemoryListRead: {
            /** Items */
            items: components["schemas"]["MemoryRead"][];
            /** Total */
            total: number;
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
        };
        /**
         * MemoryOrigin
         * @description The product flow that asked for a fact transition.
         * @enum {string}
         */
        MemoryOrigin: "automatic_formation" | "automatic_reconciliation" | "agent_tool" | "member_correction";
        /**
         * MemoryProvenance
         * @description Typed origin evidence kept separately from lifecycle ownership.
         */
        MemoryProvenance: {
            origin: components["schemas"]["MemoryOrigin"];
            /** Source Conversation Id */
            source_conversation_id?: string | null;
            /** Source Messages */
            source_messages: components["schemas"]["MemorySourceReference"][];
            actor: components["schemas"]["MemoryActor"] | null;
            /** Formation Job Id */
            formation_job_id: string | null;
            /** Reconciliation Job Id */
            reconciliation_job_id?: string | null;
            extraction: components["schemas"]["MemoryExtractionAuthority"] | null;
        };
        /** MemoryRead */
        MemoryRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Content */
            content: string;
            level: components["schemas"]["MemoryLevel"];
            /**
             * Subject Id
             * Format: uuid
             */
            subject_id: string;
            /** Subject Label */
            subject_label: string;
            status: components["schemas"]["MemoryStatus"];
            integrity: components["schemas"]["MemoryIntegrityState"];
            /**
             * Source Conversation Id
             * Format: uuid
             */
            source_conversation_id: string;
            /** Recall Count */
            recall_count: number;
            /** Last Recalled At */
            last_recalled_at: string | null;
            /** Expires At */
            expires_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** MemoryReconciliationJobRead */
        MemoryReconciliationJobRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            state: components["schemas"]["DurableState"];
            /** Generation */
            generation: number;
            /** Change Count */
            change_count: number;
            /** Considered Count */
            considered_count: number;
            /** Duplicate Count */
            duplicate_count: number;
            /** Superseded Count */
            superseded_count: number;
            /** Conflict Count */
            conflict_count: number;
            /** Unrelated Count */
            unrelated_count: number;
            /** Failed Count */
            failed_count: number;
            /** Attempts */
            attempts: number;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Last Error */
            last_error: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** MemoryReindexJobRead */
        MemoryReindexJobRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Memory Provider Config Id
             * Format: uuid
             */
            memory_provider_config_id: string;
            state: components["schemas"]["DurableState"];
            /** Source Embedding Space Id */
            source_embedding_space_id: string;
            /**
             * Target Embedding Provider Config Id
             * Format: uuid
             */
            target_embedding_provider_config_id: string;
            /** Target Embedding Provider Config Revision */
            target_embedding_provider_config_revision: number;
            /** Target Embedding Provider */
            target_embedding_provider: string;
            /** Target Embedding Model */
            target_embedding_model: string;
            /** Target Embedding Dimensions */
            target_embedding_dimensions: number;
            /** Target Embedding Semantic Options */
            target_embedding_semantic_options: {
                [key: string]: unknown;
            };
            /** Target Embedding Space Id */
            target_embedding_space_id: string;
            /** Source Fact Count */
            source_fact_count: number;
            /** Indexed Fact Count */
            indexed_fact_count: number;
            /** Attempts */
            attempts: number;
            /** Max Attempts */
            max_attempts: number;
            /** Last Error */
            last_error: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * MemoryReindexState
         * @description Operator-visible state of one Memory embedding transition.
         * @enum {string}
         */
        MemoryReindexState: "active" | "reindex_required" | "reindexing" | "failed";
        /**
         * MemoryReindexStatusRead
         * @description Current, staged, and available vector authority for one Memory config.
         */
        MemoryReindexStatusRead: {
            /** Initialized */
            initialized: boolean;
            state: components["schemas"]["MemoryReindexState"] | null;
            active_space: components["schemas"]["MemoryEmbeddingSpaceRead"] | null;
            target_space: components["schemas"]["MemoryEmbeddingSpaceRead"] | null;
            available_space: components["schemas"]["MemoryEmbeddingSpaceRead"] | null;
            /** Update Available */
            update_available: boolean;
            /** Last Error */
            last_error: string | null;
            latest_job: components["schemas"]["MemoryReindexJobRead"] | null;
        };
        /**
         * MemoryRelationshipKind
         * @enum {string}
         */
        MemoryRelationshipKind: "duplicate_of" | "superseded_by" | "conflicts_with";
        /** MemoryRelationshipRead */
        MemoryRelationshipRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["MemoryRelationshipKind"];
            memory_role: components["schemas"]["MemoryRelationshipRole"];
            /** Current */
            current: boolean;
            related_memory: components["schemas"]["MemoryRead"];
            /**
             * Reconciliation Job Id
             * Format: uuid
             */
            reconciliation_job_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * MemoryRelationshipRole
         * @enum {string}
         */
        MemoryRelationshipRole: "source" | "target";
        /**
         * MemorySort
         * @enum {string}
         */
        MemorySort: "updated_at" | "created_at" | "last_recalled_at" | "expires_at" | "recall_count";
        /**
         * MemorySourceReference
         * @description Content-free provenance for one persisted conversation message.
         */
        MemorySourceReference: {
            /**
             * Message Id
             * Format: uuid
             */
            message_id: string;
            /**
             * Participant Id
             * Format: uuid
             */
            participant_id: string;
            /** Agent Id */
            agent_id?: string | null;
            /** Agent Revision */
            agent_revision?: number | null;
        };
        /**
         * MemoryStatus
         * @enum {string}
         */
        MemoryStatus: "active" | "expired";
        /** MessageApiResponseSchema */
        MessageApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /** Externalid */
            externalId?: string | null;
            /**
             * Conversationid
             * Format: uuid
             */
            conversationId: string;
            /** Usersessionid */
            userSessionId?: string | null;
            /**
             * Senderparticipantid
             * Format: uuid
             */
            senderParticipantId: string;
            /** Agentrunid */
            agentRunId?: string | null;
            /** @default USER */
            kind: components["schemas"]["MessageKind"];
            /** @default TEXT */
            contentKind: components["schemas"]["MessageContentKind"];
            /** Content */
            content?: components["schemas"]["UserMessageContent"] | components["schemas"]["AssistantMessageContent"] | components["schemas"]["ToolUseMessageContent"] | components["schemas"]["ToolResultMessageContent"] | components["schemas"]["SystemMessageContent"] | components["schemas"]["WidgetMessageContent"] | components["schemas"]["WidgetResponseMessageContent"] | null;
            /** Parentmessageid */
            parentMessageId?: string | null;
            /** Requestid */
            requestId?: string | null;
            requestStatus?: components["schemas"]["RequestStatus"] | null;
            requestFeedback?: components["schemas"]["MessageRequestFeedback"] | null;
            meta?: components["schemas"]["MessageMeta"] | null;
            /** Htmlcontent */
            htmlContent?: string | null;
        };
        /**
         * MessageContentKind
         * @description Enum for message content types.
         * @enum {string}
         */
        MessageContentKind: "TEXT" | "AUDIO" | "IMAGE" | "TOOL" | "WIDGET" | "WIDGET_RESPONSE" | "SUMMARY" | "TASK" | "TASK_RESULT";
        /**
         * MessageKind
         * @description Enum for message categories.
         * @enum {string}
         */
        MessageKind: "USER" | "ASSISTANT" | "SYSTEM" | "TOOL_RESULT" | "TOOL_USE";
        /**
         * MessageMeta
         * @description Extensible metadata envelope for persisted messages.
         *
         *     Message producers own the specific meta schema for their subsystem. The
         *     conversation module validates that meta is object-shaped while allowing
         *     producer-owned fields to evolve without coupling conversations to agents,
         *     sockets, widgets, or integrations.
         */
        MessageMeta: {
            [key: string]: unknown;
        };
        /**
         * MessageRequestFeedback
         * @enum {string}
         */
        MessageRequestFeedback: "POSITIVE" | "NEGATIVE";
        /**
         * MessageSummary
         * @description Lightweight message representation for aggregates.
         */
        MessageSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Kind */
            kind: string;
            contentKind: components["schemas"]["MessageContentKind"];
            /** Content */
            content: components["schemas"]["UserMessageContent"] | components["schemas"]["AssistantMessageContent"] | components["schemas"]["ToolUseMessageContent"] | components["schemas"]["ToolResultMessageContent"] | components["schemas"]["SystemMessageContent"] | components["schemas"]["WidgetMessageContent"] | components["schemas"]["WidgetResponseMessageContent"];
            /**
             * Senderparticipantid
             * Format: uuid
             */
            senderParticipantId: string;
            senderKind?: components["schemas"]["ParticipantKind"] | null;
            /** Requestid */
            requestId?: string | null;
            requestFeedback?: components["schemas"]["MessageRequestFeedback"] | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Htmlcontent */
            htmlContent?: string | null;
        };
        /**
         * MisfirePolicy
         * @description What to do when several occurrences came due while nothing was running.
         * @enum {string}
         */
        MisfirePolicy: "coalesce" | "fire_all";
        /**
         * NumberPurchaseRequest
         * @description Request to purchase a phone number from a provider.
         */
        NumberPurchaseRequest: {
            /** Phonenumber */
            phoneNumber: string;
            /** Label */
            label?: string | null;
            /** Countrycode */
            countryCode?: string | null;
        };
        /**
         * NumberType
         * @description Types of phone numbers available from providers.
         * @enum {string}
         */
        NumberType: "Local" | "TollFree" | "Mobile";
        /**
         * ObjectiveCreate
         * @description Starting long-running work.
         *
         *     Both bounds are here and both are required to have a value, because an
         *     objective with neither runs until someone notices. `max_steps` stops one
         *     that loops; `deadline` stops one that is merely slow, and they catch
         *     different failures.
         */
        ObjectiveCreate: {
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /**
             * Goal
             * @description What the agent is to achieve, in your words. Kept verbatim — it is the one thing that must not drift as the work goes on.
             */
            goal: string;
            /** Max Steps */
            max_steps: number;
            /**
             * Deadline
             * Format: date-time
             */
            deadline: string;
        };
        /** ObservabilityPlan */
        ObservabilityPlan: {
            /**
             * Metrics Enabled
             * @default true
             */
            metrics_enabled: boolean;
            /**
             * Debug Events Enabled
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default false
             */
            debug_events_enabled: boolean;
            /**
             * Vendor Latency Tracking Enabled
             * @default true
             */
            vendor_latency_tracking_enabled: boolean;
        };
        /** OrganizationExecutionBudgetRead */
        OrganizationExecutionBudgetRead: {
            /** Max Concurrent Runs */
            max_concurrent_runs: number;
            /** Max Active Tokens */
            max_active_tokens: number;
            /** Max Active Milliseconds */
            max_active_milliseconds: number;
            /** Max Active Cost Microunits */
            max_active_cost_microunits: number;
            /** Run Token Limit */
            run_token_limit: number;
            /** Run Time Limit Milliseconds */
            run_time_limit_milliseconds: number;
            /** Run Cost Limit Microunits */
            run_cost_limit_microunits: number;
            /**
             * Cost Microunits Per Million Tokens
             * @description Organization-defined accounting rate used to convert metered tokens into budget microunits; it is not a provider invoice price.
             */
            cost_microunits_per_million_tokens: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** State Revision */
            state_revision: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * OrganizationExecutionBudgetUpsert
         * @description Create a first policy or replace the observed policy revision.
         */
        OrganizationExecutionBudgetUpsert: {
            /** Max Concurrent Runs */
            max_concurrent_runs: number;
            /** Max Active Tokens */
            max_active_tokens: number;
            /** Max Active Milliseconds */
            max_active_milliseconds: number;
            /** Max Active Cost Microunits */
            max_active_cost_microunits: number;
            /** Run Token Limit */
            run_token_limit: number;
            /** Run Time Limit Milliseconds */
            run_time_limit_milliseconds: number;
            /** Run Cost Limit Microunits */
            run_cost_limit_microunits: number;
            /**
             * Cost Microunits Per Million Tokens
             * @description Organization-defined accounting rate used to convert metered tokens into budget microunits; it is not a provider invoice price.
             */
            cost_microunits_per_million_tokens: number;
            /** Expected State Revision */
            expected_state_revision?: number | null;
        };
        /**
         * OrganizationVoiceConfigCreate
         * @description Create one reusable organization-owned Voice Config.
         */
        OrganizationVoiceConfigCreate: {
            /** Name */
            name: string;
            /** Description */
            description?: string | null;
            config: components["schemas"]["VoiceConfig-Input"];
        };
        /**
         * OrganizationVoiceConfigUpdate
         * @description Optimistically update the current Voice Config definition.
         */
        OrganizationVoiceConfigUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            config?: components["schemas"]["VoiceConfig-Input"] | null;
        };
        /** ParticipantApiResponseSchema */
        ParticipantApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Conversationid
             * Format: uuid
             */
            conversationId: string;
            entityKind: components["schemas"]["ParticipantKind"];
            /** Entityid */
            entityId: string;
            /** Agentid */
            agentId?: string | null;
            /** Agentrevision */
            agentRevision?: number | null;
            /**
             * Hasinitiated
             * @default false
             */
            hasInitiated: boolean;
            addedByKind?: components["schemas"]["ParticipantKind"] | null;
            /** Addedbyid */
            addedById?: string | null;
            /** Joinedat */
            joinedAt?: string | null;
            /**
             * Isactive
             * @default true
             */
            isActive: boolean;
            removedByKind?: components["schemas"]["ParticipantKind"] | null;
            /** Removedbyid */
            removedById?: string | null;
            /** Leftat */
            leftAt?: string | null;
            /** Lastreadat */
            lastReadAt?: string | null;
            /**
             * Isprimary
             * @default false
             */
            isPrimary: boolean;
        };
        /**
         * ParticipantKind
         * @description Enum for participant types.
         * @enum {string}
         */
        ParticipantKind: "AGENT" | "CONTACT" | "MEMBER";
        /**
         * ParticipantSummary
         * @description Participant with resolved entity information.
         */
        ParticipantSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            entityKind: components["schemas"]["ParticipantKind"];
            /** Entityid */
            entityId: string;
            /** Hasinitiated */
            hasInitiated: boolean;
            /** Isactive */
            isActive: boolean;
            /** Isprimary */
            isPrimary: boolean;
            /**
             * Joinedat
             * Format: date-time
             */
            joinedAt: string;
            /** Leftat */
            leftAt?: string | null;
            /** Entityname */
            entityName?: string | null;
        };
        /**
         * PhoneNumberApiResponseSchema
         * @description Schema for phone number API responses.
         */
        PhoneNumberApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * @description The ID of the organization this record belongs to.
             */
            organizationId?: string | null;
            /** Number */
            number: string;
            /** Label */
            label?: string | null;
            status: components["schemas"]["PhoneNumberStatus"];
            /** Provider */
            provider: string;
            /**
             * Providerconfigid
             * Format: uuid
             */
            providerConfigId: string;
            /** Providerconfigrevision */
            providerConfigRevision: number;
            /** Providerreference */
            providerReference?: string | null;
            /** Provisioningfailurecode */
            provisioningFailureCode?: string | null;
            /** Inboundagentid */
            inboundAgentId?: string | null;
            /** Outboundagentid */
            outboundAgentId?: string | null;
        };
        /**
         * PhoneNumberCreateSchema
         * @description Schema for creating a new phone number.
         */
        PhoneNumberCreateSchema: {
            /** Number */
            number: string;
            /** Label */
            label?: string | null;
            /** Provider */
            provider: string;
            /**
             * Providerconfigid
             * Format: uuid
             */
            providerConfigId: string;
            /** Providerconfigrevision */
            providerConfigRevision: number;
            /** Inboundagentid */
            inboundAgentId?: string | null;
            /** Outboundagentid */
            outboundAgentId?: string | null;
        };
        /**
         * PhoneNumberStatus
         * @description Enum for phone number status.
         * @enum {string}
         */
        PhoneNumberStatus: "ACTIVE" | "INACTIVE" | "PROVISIONING" | "PROVISIONING_UNKNOWN" | "PROVISIONING_FAILED";
        /**
         * PhoneNumberUpdateSchema
         * @description Schema for updating an existing phone number.
         */
        PhoneNumberUpdateSchema: {
            /** Label */
            label?: string | null;
            status?: components["schemas"]["PhoneNumberStatus"] | null;
            /** Inboundagentid */
            inboundAgentId?: string | null;
            /** Outboundagentid */
            outboundAgentId?: string | null;
        };
        /**
         * PhoneNumbersPaginated
         * @description Paginated response schema for phone numbers.
         */
        PhoneNumbersPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["PhoneNumberApiResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * PlatformToolApiSchema
         * @description Platform-native tool schema for API requests/responses.
         */
        PlatformToolApiSchema: {
            /**
             * Name
             * @description Unique tool name for the LLM to reference
             */
            name: string;
            /**
             * Description
             * @description Clear description of what the tool does for the LLM
             */
            description: string;
            /** @description JSON Schema defining the tool's input parameters */
            inputSchema: components["schemas"]["PlatformToolInputApiSchema"];
        };
        /**
         * PlatformToolInputApiSchema
         * @description Platform tool input schema with camelCase aliases for API.
         */
        PlatformToolInputApiSchema: {
            /**
             * Type
             * @default object
             * @constant
             */
            type: "object";
            /**
             * Properties
             * @description JSON Schema properties for tool inputs
             */
            properties?: {
                [key: string]: unknown;
            };
            /**
             * $Defs
             * @description Reusable JSON Schema definitions referenced by $ref.
             */
            $defs?: {
                [key: string]: unknown;
            } | null;
            /**
             * Required
             * @description Required property names
             */
            required?: string[] | null;
            /**
             * Oneof
             * @description Alternative component-specific schemas for this tool input.
             */
            oneOf?: {
                [key: string]: unknown;
            }[] | null;
            /**
             * Discriminator
             * @description JSON Schema discriminator metadata for union-style tool inputs.
             */
            discriminator?: {
                [key: string]: unknown;
            } | null;
            /**
             * Additionalproperties
             * @description Whether additional properties are allowed
             */
            additionalProperties?: boolean | null;
        };
        /**
         * ProviderConfigApiResponseSchema
         * @description Secret-safe telephony config lifecycle response.
         */
        ProviderConfigApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
            /** Operations */
            operations: {
                [key: string]: boolean;
            };
        };
        /** ProviderConfigCreateSchema */
        ProviderConfigCreateSchema: {
            provider: components["schemas"]["TelephonyProvider"];
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** ProviderConfigUpdateSchema */
        ProviderConfigUpdateSchema: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** ProviderConfigVerificationResponse */
        ProviderConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /** ProviderDefinition */
        ProviderDefinition: {
            /** Id */
            id: string;
            /** Label */
            label: string;
            /** Description */
            description?: string | null;
            /** Fields */
            fields: components["schemas"]["ProviderFieldDefinition"][];
            /**
             * Require One Of
             * @default []
             */
            require_one_of: string[][];
        };
        /** ProviderFieldCondition */
        ProviderFieldCondition: {
            /** Field */
            field: string;
            /** Equals */
            equals: string | boolean;
        };
        /** ProviderFieldDefinition */
        ProviderFieldDefinition: {
            /** Key */
            key: string;
            /** Wire Key */
            wire_key: string;
            /** Label */
            label: string;
            /** Description */
            description?: string | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "text" | "password" | "integer" | "number" | "boolean" | "select" | "string_list" | "provider_config";
            /**
             * Target
             * @default config
             * @enum {string}
             */
            target: "config" | "secrets";
            /**
             * Required
             * @default false
             */
            required: boolean;
            /**
             * Secret
             * @default false
             */
            secret: boolean;
            /**
             * Multiline
             * @default false
             */
            multiline: boolean;
            /**
             * Options
             * @default []
             */
            options: components["schemas"]["ProviderFieldOption"][];
            /**
             * Allow Custom
             * @default false
             */
            allow_custom: boolean;
            /** Minimum */
            minimum?: number | null;
            /** Maximum */
            maximum?: number | null;
            visible_when?: components["schemas"]["ProviderFieldCondition"] | null;
            required_when?: components["schemas"]["ProviderFieldCondition"] | null;
            reference_capability?: components["schemas"]["Capability"] | null;
        };
        /** ProviderFieldOption */
        ProviderFieldOption: {
            /** Value */
            value: string;
            /** Label */
            label: string;
        };
        /** ProviderOnboardingCatalogResponse */
        ProviderOnboardingCatalogResponse: {
            /** Capabilities */
            capabilities: components["schemas"]["CapabilityDefinition"][];
        };
        /** RecordingListResponse */
        RecordingListResponse: {
            /** Recordings */
            recordings: components["schemas"]["VoiceRecordingResponse"][];
        };
        /** RegistrationRequestSchema */
        RegistrationRequestSchema: {
            /**
             * Password
             * @description Member's password
             */
            password: string;
            /**
             * Email
             * Format: email
             * @description Member's email address
             */
            email: string;
        };
        /**
         * ReplaceCuratedToolGrantsRequestSchema
         * @description Exact curated-tool selection plus its optimistic-concurrency guard.
         */
        ReplaceCuratedToolGrantsRequestSchema: {
            /** Toolids */
            toolIds: string[];
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /**
         * RequestStatus
         * @description Enum for message request lifecycle status.
         *
         *     Lifecycle flow:
         *     - PENDING → PROCESSING → AWAITING_TOOL_RESULTS → PROCESSING → COMPLETED
         *     - PENDING/PROCESSING → INTERRUPTED (when new user message arrives)
         *     - Any state → FAILED (on error)
         *
         *     INTERRUPTED status indicates the request was superseded by a newer request
         *     and should be ignored in LLM context and TTS output.
         *
         *     SKIPPED indicates the worker picked the task up and decided no work was
         *     needed. Like INTERRUPTED it should be ignored in LLM context and TTS
         *     output, but it is not a failure and not a supersession.
         * @enum {string}
         */
        RequestStatus: "PENDING" | "PROCESSING" | "AWAITING_TOOL_RESULTS" | "COMPLETED" | "FAILED" | "INTERRUPTED" | "SKIPPED";
        /** RerankingConfigCreate */
        RerankingConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** RerankingConfigResponse */
        RerankingConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** RerankingConfigUpdate */
        RerankingConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** RerankingConfigVerificationResponse */
        RerankingConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /**
         * ResetPasswordRequestSchema
         * @description Request schema for resetting a password with a token.
         */
        ResetPasswordRequestSchema: {
            /**
             * Token
             * @description Reset JWT token
             */
            token: string;
            /**
             * Newpassword
             * @description New password
             */
            newPassword: string;
        };
        /**
         * RevisionAvailability
         * @description Availability of an immutable revision.
         *
         *     Ordinary withdrawal belongs to the stable header so already pinned work can
         *     continue. Emergency revocation belongs to the exact revision and blocks
         *     both new selection and pinned resume.
         * @enum {string}
         */
        RevisionAvailability: "published" | "revoked";
        /**
         * SandboxAccess
         * @description What an agent may do with a sandbox.
         *
         *     V1 exposes only bounded no-egress compute. A networked value would be a
         *     promise that the Docker adapter cannot enforce safely.
         * @enum {string}
         */
        SandboxAccess: "run";
        /** SandboxConfigCreate */
        SandboxConfigCreate: {
            /**
             * Provider
             * @constant
             */
            provider: "docker";
            /** Name */
            name: string;
            config: components["schemas"]["SandboxConfigSettings"];
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** SandboxConfigResponse */
        SandboxConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            config: components["schemas"]["SandboxConfigSettings"];
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /**
         * SandboxConfigSettings
         * @description Docker V1 fields; every security/resource choice is explicit.
         */
        SandboxConfigSettings: {
            /** Endpoint */
            endpoint: string;
            /** Image */
            image: string;
            /** Memorymb */
            memoryMb: number;
            /** Cpucores */
            cpuCores: number;
            /** Diskmb */
            diskMb: number;
            /** Pids */
            pids: number;
            /** Ttlseconds */
            ttlSeconds: number;
            /** Commandtimeoutseconds */
            commandTimeoutSeconds: number;
            /** Maxoutputbytes */
            maxOutputBytes: number;
            /** Maxsessions */
            maxSessions: number;
            /**
             * Network
             * @constant
             */
            network: false;
        };
        /** SandboxConfigUpdate */
        SandboxConfigUpdate: {
            /** Name */
            name?: string | null;
            config?: components["schemas"]["SandboxConfigSettings"] | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** SandboxConfigVerificationResponse */
        SandboxConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /**
         * SandboxGrantCreate
         * @description Bind an agent to one explicit ready no-egress sandbox config.
         */
        SandboxGrantCreate: {
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /**
             * Sandbox Provider Config Id
             * Format: uuid
             */
            sandbox_provider_config_id: string;
            /**
             * Access
             * @constant
             */
            access: "run";
            /**
             * Max Sessions
             * @description How many workspaces this agent may hold at once. Narrows the organization's limit; it cannot exceed it.
             */
            max_sessions?: number | null;
        };
        /** SandboxGrantRead */
        SandboxGrantRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            access: components["schemas"]["SandboxAccess"];
            /**
             * Sandbox Provider Config Id
             * Format: uuid
             */
            sandbox_provider_config_id: string;
            /** Sandbox Provider Config Revision */
            sandbox_provider_config_revision: number;
            /** Revision */
            revision: number;
            /** Max Sessions */
            max_sessions: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** SandboxSessionRead */
        SandboxSessionRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Image */
            image: string;
            /**
             * Sandbox Provider Config Id
             * Format: uuid
             */
            sandbox_provider_config_id: string;
            /** Sandbox Provider Config Revision */
            sandbox_provider_config_revision: number;
            /** Grant Id */
            grant_id: string | null;
            /** Grant Revision */
            grant_revision: number | null;
            /** Effective Policy */
            effective_policy: {
                [key: string]: unknown;
            };
            state: components["schemas"]["SandboxState"];
            /** Agent Id */
            agent_id: string | null;
            /** Agent Run Id */
            agent_run_id: string | null;
            /** Workspace */
            workspace: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Last Used At */
            last_used_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * SandboxState
         * @description Where a session is in its life.
         * @enum {string}
         */
        SandboxState: "starting" | "running" | "paused" | "stopped" | "destroyed";
        /** ScheduleCreate */
        ScheduleCreate: {
            /** Name */
            name: string;
            /** Action */
            action: string;
            /** Payload */
            payload?: {
                [key: string]: unknown;
            };
            /**
             * Agent Id
             * Format: uuid
             * @description Agent whose current published revision is pinned by this explicit create/update. Every schedule triggers an agent; there is no platform/default executor.
             */
            agent_id: string;
            /**
             * Timezone
             * @description IANA name, e.g. 'Europe/Berlin'. Occurrences are computed in it.
             */
            timezone: string;
            /**
             * Starts At
             * Format: date-time
             * @description The anchor. Also the wall-clock time each occurrence lands on.
             */
            starts_at: string;
            /**
             * Rule
             * @description RFC 5545 RRULE without DTSTART, e.g. 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'. Omit for a one-shot.
             */
            rule?: string | null;
            /** Ends At */
            ends_at?: string | null;
            /** @default coalesce */
            misfire_policy: components["schemas"]["MisfirePolicy"];
            /**
             * Key
             * @description Stable id, unique per organization. Re-creating this key is a conflict; use the explicit expected-revision update endpoint.
             */
            key: string;
        };
        /** ScheduleRead */
        ScheduleRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            /** Name */
            name: string;
            /** Action */
            action: string;
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            /** Rule */
            rule: string | null;
            /** Timezone */
            timezone: string;
            /**
             * Starts At
             * Format: date-time
             */
            starts_at: string;
            /** Ends At */
            ends_at: string | null;
            misfire_policy: components["schemas"]["MisfirePolicy"];
            /** Enabled */
            enabled: boolean;
            /** Published Revision */
            published_revision: number;
            /** Lifecycle */
            lifecycle: string;
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /** Agent Revision */
            agent_revision: number;
            /** Next At */
            next_at: string | null;
            /** Last Fired At */
            last_fired_at: string | null;
            /** Retired At */
            retired_at: string | null;
            /** Last Error */
            last_error: string | null;
        };
        /** ScheduleRevisionRevoke */
        ScheduleRevisionRevoke: {
            /** Reason */
            reason: string;
        };
        /** ScheduleRunRead */
        ScheduleRunRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /** Schedule Revision */
            schedule_revision: number;
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /** Agent Revision */
            agent_revision: number;
            /**
             * Scheduled For
             * Format: date-time
             */
            scheduled_for: string;
            /** Action */
            action: string;
            /**
             * Agent Run Id
             * Format: uuid
             */
            agent_run_id: string;
            lifecycle: components["schemas"]["AgentRunLifecycle"];
            outcome: components["schemas"]["AgentRunOutcome"] | null;
            /** Misfired Count */
            misfired_count: number;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Result */
            result: {
                [key: string]: unknown;
            } | null;
            /** Failure Summary */
            failure_summary: string | null;
        };
        /** ScheduleUpdate */
        ScheduleUpdate: {
            /** Name */
            name: string;
            /** Action */
            action: string;
            /** Payload */
            payload?: {
                [key: string]: unknown;
            };
            /**
             * Agent Id
             * Format: uuid
             * @description Agent whose current published revision is pinned by this explicit create/update. Every schedule triggers an agent; there is no platform/default executor.
             */
            agent_id: string;
            /**
             * Timezone
             * @description IANA name, e.g. 'Europe/Berlin'. Occurrences are computed in it.
             */
            timezone: string;
            /**
             * Starts At
             * Format: date-time
             * @description The anchor. Also the wall-clock time each occurrence lands on.
             */
            starts_at: string;
            /**
             * Rule
             * @description RFC 5545 RRULE without DTSTART, e.g. 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'. Omit for a one-shot.
             */
            rule?: string | null;
            /** Ends At */
            ends_at?: string | null;
            /** @default coalesce */
            misfire_policy: components["schemas"]["MisfirePolicy"];
            /** Expected Revision */
            expected_revision: number;
        };
        /** ServerConfig */
        ServerConfig: {
            /**
             * Webhook Url
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            webhook_url?: string | null;
            /**
             * Webhook Events
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            webhook_events?: string[];
            /**
             * Webhook Timeout Ms
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default 30000
             */
            webhook_timeout_ms: number;
            /**
             * Headers
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            headers?: {
                [key: string]: string;
            };
        };
        /**
         * SessionValidationRequest
         * @description Request payload for session validation.
         */
        SessionValidationRequest: {
            /**
             * Organizationid
             * Format: uuid
             * @description Organization UUID
             */
            organizationId: string;
            /**
             * Sessiontoken
             * @description Session token from auth_sessions
             */
            sessionToken: string;
            /**
             * Contactid
             * Format: uuid
             * @description Contact UUID
             */
            contactId: string;
            /**
             * Conversationid
             * Format: uuid
             * @description Conversation UUID
             */
            conversationId: string;
        };
        /**
         * SessionValidationResponse
         * @description Response payload for successful session validation.
         */
        SessionValidationResponse: {
            /** Organizationid */
            organizationId: string;
            /** Sessiontoken */
            sessionToken: string;
            contact: components["schemas"]["ContactApiResponseSchema"];
            conversation: components["schemas"]["ConversationApiResponseSchema"];
        };
        /**
         * SetExecutionModeRequestSchema
         * @description Operator policy for one curated tool.
         */
        SetExecutionModeRequestSchema: {
            executionMode: components["schemas"]["eylo__modules__integrations_v2__domain__enums__ToolExecutionMode"];
        };
        /**
         * SilenceConfig
         * @description Silence detection and response behavior.
         */
        SilenceConfig: {
            /**
             * Reminder Trigger Ms
             * @description Milliseconds of silence before a reminder is spoken.
             * @default 10000
             */
            reminder_trigger_ms: number;
            /**
             * Reminder Max Count
             * @description Maximum number of reminders before ending the call.
             * @default 2
             */
            reminder_max_count: number;
            /**
             * Reminder Messages
             * @description Messages to use as silence reminders (cycled in order).
             */
            reminder_messages?: string[];
            /**
             * End Call After Silence Ms
             * @description End call after this many ms of total silence. 0 = disabled.
             * @default 0
             */
            end_call_after_silence_ms: number;
        };
        /**
         * SortDirection
         * @enum {string}
         */
        SortDirection: "asc" | "desc";
        /** StartSpeakingPlan */
        StartSpeakingPlan: {
            /**
             * Wait Ms
             * @description Number of milliseconds to wait before starting to speak.
             * @default 0
             */
            wait_ms: number;
            /**
             * Responsiveness
             * @default 0.5
             */
            responsiveness: number;
            /**
             * Begin Message Delay Ms
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default 0
             */
            begin_message_delay_ms: number;
        };
        /** StopSpeakingPlan */
        StopSpeakingPlan: {
            /**
             * @description Type of interruption.
             * @default transcript
             */
            interruption_type: components["schemas"]["InterruptionType"];
            /**
             * Num Words
             * @description Minimum word count before allowing interruption. 0 = interrupt on any speech.
             * @default 0
             */
            num_words: number;
            /**
             * Voice Seconds
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default 0
             */
            voice_seconds: number;
            /**
             * Backoff Seconds
             * @description Cooldown period after an interruption before allowing another.
             * @default 0
             */
            backoff_seconds: number;
            /**
             * Interruption Sensitivity
             * @description Normalized interruption sensitivity. Higher values interrupt more eagerly.
             * @default 0.5
             */
            interruption_sensitivity: number;
            /** Acknowledgement Phrases */
            acknowledgement_phrases?: string[];
            /** Interruption Phrases */
            interruption_phrases?: string[];
        };
        /** StorageCapabilitiesResponse */
        StorageCapabilitiesResponse: {
            /** Upload */
            upload: boolean;
            /** List */
            list: boolean;
            /** Download */
            download: boolean;
            /** Delete */
            delete: boolean;
            /** Presigneddownload */
            presignedDownload: boolean;
        };
        /** StorageConfigCreate */
        StorageConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** StorageConfigResponse */
        StorageConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
            capabilities: components["schemas"]["StorageCapabilitiesResponse"];
        };
        /** StorageConfigUpdate */
        StorageConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** StorageConfigVerificationResponse */
        StorageConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
            capabilities: components["schemas"]["StorageCapabilitiesResponse"];
        };
        /** SystemMessageContent */
        SystemMessageContent: {
            /**
             * Role
             * @default system
             * @constant
             */
            role: "system";
            /**
             * Content
             * @description System message blocks
             */
            content: (components["schemas"]["TextContent"] | components["schemas"]["ImageUrlContent"])[];
        };
        /**
         * TelephonyCallApiResponseSchema
         * @description Minimal public projection backed by canonical call writers.
         */
        TelephonyCallApiResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /** Callsid */
            callSid?: string | null;
            /** Provider */
            provider: string;
            /**
             * Providerconfigid
             * Format: uuid
             */
            providerConfigId: string;
            /** Providerconfigrevision */
            providerConfigRevision: number;
            /** Direction */
            direction: string;
            /** Status */
            status: string;
            /** Fromnumber */
            fromNumber?: string | null;
            /** Tonumber */
            toNumber?: string | null;
            /** Endedreason */
            endedReason?: string | null;
            /** Agentid */
            agentId?: string | null;
            /** Agentrevision */
            agentRevision?: number | null;
            /** Conversationid */
            conversationId?: string | null;
            /** Campaignid */
            campaignId?: string | null;
            /** Campaigncontactid */
            campaignContactId?: string | null;
            /** Campaignattemptid */
            campaignAttemptId?: string | null;
            /** Phonenumberid */
            phoneNumberId?: string | null;
            /** Voicesessionid */
            voiceSessionId?: string | null;
            /** Startedat */
            startedAt?: string | null;
            /** Connectedat */
            connectedAt?: string | null;
            /** Endedat */
            endedAt?: string | null;
            /** Durationseconds */
            durationSeconds?: number | null;
            /** Providerstatus */
            providerStatus?: string | null;
            /** Openerdeliverystatus */
            openerDeliveryStatus: string;
            /** Openerdeliveredat */
            openerDeliveredAt?: string | null;
            /** Transferstatus */
            transferStatus: string;
            /** Transferto */
            transferTo?: string | null;
            /** Transferreason */
            transferReason?: string | null;
            /** Transferredat */
            transferredAt?: string | null;
        };
        /**
         * TelephonyCallsPaginated
         * @description Paginated response schema for telephony calls.
         */
        TelephonyCallsPaginated: {
            /**
             * Page
             * @description Page number, starting from 1
             * @default 1
             */
            page: number;
            /**
             * Limit
             * @description Number of items per page
             * @default 10
             */
            limit: number;
            /**
             * Total
             * @description Total number of items available (optional for client-side use)
             */
            total?: number | null;
            /** Data */
            data: components["schemas"]["TelephonyCallApiResponseSchema"][];
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean | null;
        };
        /**
         * TelephonyOperation
         * @description Carrier operations exposed by the common telephony contract.
         * @enum {string}
         */
        TelephonyOperation: "search_numbers" | "purchase_number" | "release_number" | "inbound_call" | "outbound_call" | "bidirectional_media" | "end_call" | "transfer_call" | "receive_dtmf" | "send_dtmf" | "authenticated_status_callback";
        /**
         * TelephonyProvider
         * @enum {string}
         */
        TelephonyProvider: "twilio" | "plivo" | "vonage" | "exotel";
        /**
         * TemplateConsumerKind
         * @enum {string}
         */
        TemplateConsumerKind: "conversational_text" | "realtime_voice" | "background_agent" | "swarm_agent" | "sandbox_agent" | "campaign_message";
        /** TemplateCreateRequest */
        TemplateCreateRequest: {
            /** Name */
            name: string;
            kind: components["schemas"]["TemplateKind"];
            /** Body */
            body: string;
            variable_schema: components["schemas"]["TemplateVariablesSchema-Input"];
        };
        /** TemplateDraftUpdateRequest */
        TemplateDraftUpdateRequest: {
            /** Expected Draft Version */
            expected_draft_version: number;
            /** Body */
            body?: string | null;
            variable_schema?: components["schemas"]["TemplateVariablesSchema-Input"] | null;
        };
        /**
         * TemplateKind
         * @enum {string}
         */
        TemplateKind: "agent_instructions" | "campaign_message";
        /** TemplatePreviewRequest */
        TemplatePreviewRequest: {
            consumer_kind: components["schemas"]["TemplateConsumerKind"];
            /** Variables */
            variables: {
                [key: string]: unknown;
            };
        };
        /** TemplatePublishRequest */
        TemplatePublishRequest: {
            /** Expected Draft Version */
            expected_draft_version: number;
        };
        /** TemplateRenderRequest */
        TemplateRenderRequest: {
            consumer_kind: components["schemas"]["TemplateConsumerKind"];
            /** Variables */
            variables: {
                [key: string]: unknown;
            };
        };
        /** TemplateRenderResponse */
        TemplateRenderResponse: {
            /**
             * Template Id
             * Format: uuid
             */
            template_id: string;
            /** Revision */
            revision?: number | null;
            /** Draft Version */
            draft_version?: number | null;
            /** Renderer Version */
            renderer_version: string;
            consumer_kind: components["schemas"]["TemplateConsumerKind"];
            /** Variable Names */
            variable_names: string[];
            /** Text */
            text: string;
            /** Segments */
            segments: components["schemas"]["TemplateSegmentResponse"][];
        };
        /** TemplateResponse */
        TemplateResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            kind: components["schemas"]["TemplateKind"];
            lifecycle: components["schemas"]["DefinitionLifecycle"];
            /** Published Revision */
            published_revision: number | null;
            /** Draft Version */
            draft_version: number;
            /** Draft Dirty */
            draft_dirty: boolean;
            /** Draft Body */
            draft_body: string;
            draft_variable_schema: components["schemas"]["TemplateVariablesSchema-Output"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** TemplateRevisionResponse */
        TemplateRevisionResponse: {
            /**
             * Template Id
             * Format: uuid
             */
            template_id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Revision */
            revision: number;
            kind: components["schemas"]["TemplateKind"];
            /** Body */
            body: string;
            variable_schema: components["schemas"]["TemplateVariablesSchema-Output"];
            /** Renderer Version */
            renderer_version: string;
            availability: components["schemas"]["RevisionAvailability"];
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Revoked At */
            revoked_at: string | null;
            /** Revoked By */
            revoked_by: string | null;
            /** Revocation Reason */
            revocation_reason: string | null;
            /** Cancellation Requested At */
            cancellation_requested_at: string | null;
        };
        /** TemplateRevokeRequest */
        TemplateRevokeRequest: {
            /** Reason */
            reason: string;
        };
        /**
         * TemplateSegmentAuthority
         * @enum {string}
         */
        TemplateSegmentAuthority: "authored_instruction" | "runtime_data";
        /** TemplateSegmentResponse */
        TemplateSegmentResponse: {
            authority: components["schemas"]["TemplateSegmentAuthority"];
            /** Text */
            text: string;
            /** Variable Name */
            variable_name: string | null;
        };
        /** TemplateVariableSchema */
        TemplateVariableSchema: {
            /** Name */
            name: string;
            type: components["schemas"]["TemplateVariableType"];
        };
        /**
         * TemplateVariableType
         * @enum {string}
         */
        TemplateVariableType: "string" | "integer" | "number" | "boolean";
        /** TemplateVariablesSchema */
        "TemplateVariablesSchema-Input": {
            /** Variables */
            variables: components["schemas"]["TemplateVariableSchema"][];
        };
        /** TemplateVariablesSchema */
        "TemplateVariablesSchema-Output": {
            /** Variables */
            variables: components["schemas"]["TemplateVariableSchema"][];
        };
        /**
         * TextContent
         * @description Text content block in a message.
         */
        TextContent: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "text";
            /**
             * Text
             * @description The text content
             */
            text: string;
        };
        /**
         * TimelineCategory
         * @enum {string}
         */
        TimelineCategory: "session" | "conversation" | "message" | "agent" | "tool" | "file" | "voice" | "telephony" | "technical";
        /**
         * TimelineSeverity
         * @enum {string}
         */
        TimelineSeverity: "default" | "danger";
        /**
         * TokenResponseSchema
         * @description Schema for authentication token.
         */
        TokenResponseSchema: {
            /**
             * Accesstoken
             * @description JWT access token
             */
            accessToken: string;
            /**
             * Tokentype
             * @description Token type
             * @default bearer
             */
            tokenType: string;
        };
        /** ToolCreateRequestSchema */
        ToolCreateRequestSchema: {
            /**
             * Name
             * @description Tool name
             */
            name: string;
            /** @description Tool execution boundary */
            kind: components["schemas"]["ToolKind"];
            /**
             * Displayname
             * @description Tool display name
             */
            displayName: string;
            /**
             * Description
             * @description Tool description
             */
            description: string;
            /**
             * Mcpserverid
             * @description MCP server ID
             */
            mcpServerId?: string | null;
            /** Wireid */
            wireId?: string | null;
            /** @description LLM schema for the tool */
            llmConfig?: components["schemas"]["PlatformToolApiSchema"] | null;
            /**
             * Executorconfig
             * @description Executor schema for the tool
             */
            executorConfig?: {
                [key: string]: unknown;
            } | null;
            /** Outputschema */
            outputSchema?: {
                [key: string]: unknown;
            } | null;
            /** @default auto */
            executionMode: components["schemas"]["eylo__modules__tools__models__ToolExecutionMode"];
        };
        /**
         * ToolEffect
         * @description Whether one curated tool may change vendor-side state.
         *
         *     This drives durability, not documentation. A `MUTATION` tool is refused
         *     execution without a committed `TOOL_USE` owner and a durable context; a
         *     `READ` tool is executed directly and writes no outbound receipt.
         * @enum {string}
         */
        ToolEffect: "read" | "mutation";
        /**
         * ToolKind
         * @description Execution boundary for a tool exposed to an agent.
         * @enum {string}
         */
        ToolKind: "LOCAL" | "SYSTEM" | "MCP" | "CURATED";
        /** ToolListResponseSchema */
        ToolListResponseSchema: {
            /** Items */
            items: components["schemas"]["ToolResponseSchema"][];
        };
        /** ToolPublishRequestSchema */
        ToolPublishRequestSchema: {
            /** Expecteddraftversion */
            expectedDraftVersion: number;
        };
        /** ToolResponseSchema */
        ToolResponseSchema: {
            /**
             * Id
             * Format: uuid
             * @description Auto-generated unique identifier
             */
            id: string;
            /**
             * Deleted
             * @description Whether the record is active
             * @default true
             */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             * @description Record creation timestamp
             */
            createdAt?: string;
            /**
             * Updatedat
             * Format: date-time
             * @description Record last update timestamp
             */
            updatedAt?: string;
            /**
             * Externalid
             * @description External Service identifier
             */
            externalId?: string | null;
            /**
             * Organizationid
             * @description The ID of the organization this record belongs to.
             */
            organizationId?: string | null;
            /**
             * Name
             * @description Tool name
             */
            name: string;
            /**
             * Slug
             * @description Tool slug
             */
            slug: string;
            /** @description Tool execution boundary */
            kind: components["schemas"]["ToolKind"];
            /**
             * Displayname
             * @description Tool display name
             */
            displayName: string;
            /**
             * Description
             * @description Tool description
             */
            description: string;
            /**
             * Mcpserverid
             * @description MCP server ID
             */
            mcpServerId?: string | null;
            /** Mcpserverrevision */
            mcpServerRevision?: number | null;
            /** Wireid */
            wireId?: string | null;
            /** @default draft */
            lifecycle: components["schemas"]["DefinitionLifecycle"];
            /** Publishedrevision */
            publishedRevision?: number | null;
            /**
             * Draftversion
             * @default 1
             */
            draftVersion: number;
            /**
             * Draftdirty
             * @default true
             */
            draftDirty: boolean;
            /** @default auto */
            executionMode: components["schemas"]["eylo__modules__tools__models__ToolExecutionMode"];
            /** @description LLM schema for the tool */
            llmConfig?: components["schemas"]["PlatformToolApiSchema"] | null;
            /**
             * Executorconfig
             * @description Executor schema for the tool
             */
            executorConfig?: {
                [key: string]: unknown;
            } | null;
            /** Outputschema */
            outputSchema?: {
                [key: string]: unknown;
            } | null;
        };
        /**
         * ToolResultContent
         * @description Tool result content - represents the result of tool execution.
         *
         *     This is stored when a tool execution completes.
         *     Database format for TOOL_RESULT messages.
         */
        ToolResultContent: {
            /**
             * Type
             * @default tool_result
             * @constant
             */
            type: "tool_result";
            /**
             * Tool Use Id
             * @description ID of the tool use this result corresponds to
             */
            tool_use_id: string;
            /**
             * Content
             * @description Tool execution result - can be string, dict, list, etc.
             */
            content: unknown;
            /**
             * Name
             * @description Name of the tool that was executed
             */
            name?: string | null;
            /**
             * Is Error
             * @description Whether execution failed
             * @default false
             */
            is_error: boolean;
        };
        /**
         * ToolResultMessageContent
         * @description Content structure for TOOL_RESULT messages in database.
         *
         *     Database format: {"role": "user", "content": [{...}]}
         */
        ToolResultMessageContent: {
            /**
             * Role
             * @default user
             * @constant
             */
            role: "user";
            /**
             * Content
             * @description List of tool results (usually one)
             */
            content: components["schemas"]["ToolResultContent"][];
        };
        /** ToolRevisionResponseSchema */
        ToolRevisionResponseSchema: {
            /**
             * Tool Id
             * Format: uuid
             */
            tool_id: string;
            /** Revision */
            revision: number;
            availability: components["schemas"]["RevisionAvailability"];
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Published By */
            published_by: string | null;
            /** Revoked At */
            revoked_at: string | null;
            /** Revoked By */
            revoked_by: string | null;
            /** Revocation Reason */
            revocation_reason: string | null;
            /** Cancellation Requested At */
            cancellation_requested_at: string | null;
        };
        /** ToolRevokeRequestSchema */
        ToolRevokeRequestSchema: {
            /** Reason */
            reason: string;
        };
        /** ToolUpdateRequestSchema */
        ToolUpdateRequestSchema: {
            /** Expecteddraftversion */
            expectedDraftVersion: number;
            /**
             * Name
             * @description Tool name
             */
            name?: string | null;
            /**
             * Displayname
             * @description Tool display name
             */
            displayName?: string | null;
            /**
             * Description
             * @description Tool description
             */
            description?: string | null;
            /** @description LLM schema for the tool */
            llmConfig?: components["schemas"]["PlatformToolApiSchema"] | null;
            /**
             * Executorconfig
             * @description Executor schema for the tool
             */
            executorConfig?: {
                [key: string]: unknown;
            } | null;
            /** Outputschema */
            outputSchema?: {
                [key: string]: unknown;
            } | null;
            executionMode?: components["schemas"]["eylo__modules__tools__models__ToolExecutionMode"] | null;
        };
        /**
         * ToolUseContent
         * @description Tool use content - represents a request to execute a tool.
         *
         *     This is stored when an LLM requests to use a tool.
         *     Database format for TOOL_USE messages.
         */
        ToolUseContent: {
            /**
             * Type
             * @default tool_use
             * @constant
             */
            type: "tool_use";
            /**
             * Id
             * @description Unique identifier for this tool use
             */
            id: string;
            /**
             * Name
             * @description Name of the tool to execute
             */
            name: string;
            /**
             * Input
             * @description Input parameters for the tool
             */
            input?: {
                [key: string]: unknown;
            };
        };
        /**
         * ToolUseMessageContent
         * @description Content structure for TOOL_USE messages in database.
         *
         *     Database format: {"role": "tool_use", "content": {...}}
         */
        ToolUseMessageContent: {
            /**
             * Role
             * @default tool_use
             * @constant
             */
            role: "tool_use";
            /** @description Tool use details */
            content: components["schemas"]["ToolUseContent"];
        };
        /** TransportConfig */
        TransportConfig: {
            /**
             * Browser Transport
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default webrtc
             * @enum {string}
             */
            browser_transport: "webrtc" | "websocket";
            /**
             * Telephony Provider
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             */
            telephony_provider?: string | null;
            /**
             * Ring Duration Ms
             * @description EXPERIMENTAL — stored but not yet enforced. Setting this has no effect on behaviour.
             * @default 30000
             */
            ring_duration_ms: number;
            keypad_input?: components["schemas"]["KeypadInputPlan"];
        };
        /** UnsupportedConsumerHealthResponse */
        UnsupportedConsumerHealthResponse: {
            /** Consumer Name */
            consumer_name: string;
            /** Event Type */
            event_type: string;
            /** Event Version */
            event_version: number;
            /** Delivery Count */
            delivery_count: number;
        };
        /**
         * UserMessageContent
         * @description Content structure for USER messages in database.
         *
         *     Database format: {"role": "user", "content": [{"type": "text", ...}, ...]}
         */
        UserMessageContent: {
            /**
             * Role
             * @default user
             * @constant
             */
            role: "user";
            /**
             * Content
             * @description Message content blocks
             */
            content: (components["schemas"]["TextContent"] | components["schemas"]["ImageUrlContent"])[];
        };
        /** UserSessionContactRead */
        UserSessionContactRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name?: string | null;
            /** Primaryemail */
            primaryEmail?: string | null;
            /** Primaryphone */
            primaryPhone?: string | null;
        };
        /** UserSessionCountsRead */
        UserSessionCountsRead: {
            /**
             * Conversations
             * @default 0
             */
            conversations: number;
            /**
             * Messages
             * @default 0
             */
            messages: number;
            /**
             * Agentruns
             * @default 0
             */
            agentRuns: number;
            /**
             * Voicesessions
             * @default 0
             */
            voiceSessions: number;
            /**
             * Telephonycalls
             * @default 0
             */
            telephonyCalls: number;
            /**
             * Timelineevents
             * @default 0
             */
            timelineEvents: number;
        };
        /**
         * UserSessionEntryChannel
         * @enum {string}
         */
        UserSessionEntryChannel: "widget" | "telephony" | "api";
        /** UserSessionPage */
        UserSessionPage: {
            /** Items */
            items: components["schemas"]["UserSessionRead"][];
            /** Page */
            page: number;
            /** Limit */
            limit: number;
            /** Total */
            total: number;
        };
        /** UserSessionRead */
        UserSessionRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            contact: components["schemas"]["UserSessionContactRead"];
            entryChannel: components["schemas"]["UserSessionEntryChannel"];
            state: components["schemas"]["UserSessionState"];
            /** Connectionsequence */
            connectionSequence: number;
            /**
             * Startedat
             * Format: date-time
             */
            startedAt: string;
            /**
             * Lastactivityat
             * Format: date-time
             */
            lastActivityAt: string;
            /** Disconnectedat */
            disconnectedAt?: string | null;
            /** Endedat */
            endedAt?: string | null;
            /** Endreason */
            endReason?: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            counts: components["schemas"]["UserSessionCountsRead"];
        };
        /**
         * UserSessionSortDirection
         * @enum {string}
         */
        UserSessionSortDirection: "asc" | "desc";
        /**
         * UserSessionSortField
         * @enum {string}
         */
        UserSessionSortField: "started_at" | "last_activity_at" | "state" | "contact";
        /**
         * UserSessionState
         * @enum {string}
         */
        UserSessionState: "active" | "disconnected" | "ended" | "failed";
        /** UserSessionTimelineEventRead */
        UserSessionTimelineEventRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            category: components["schemas"]["TimelineCategory"];
            /** Eventtype */
            eventType: string;
            /** Label */
            label: string;
            severity: components["schemas"]["TimelineSeverity"];
            /** Technical */
            technical: boolean;
            /** Subjecttype */
            subjectType: string;
            /**
             * Subjectid
             * Format: uuid
             */
            subjectId: string;
            /**
             * Occurredat
             * Format: date-time
             */
            occurredAt: string;
            /**
             * Recordedat
             * Format: date-time
             */
            recordedAt: string;
            /** Causationid */
            causationId?: string | null;
            /** Details */
            details?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** UserSessionTimelinePage */
        UserSessionTimelinePage: {
            /** Items */
            items: components["schemas"]["UserSessionTimelineEventRead"][];
            /** Page */
            page: number;
            /** Limit */
            limit: number;
            /** Total */
            total: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /**
         * VendorAuthKind
         * @description How an organization proves identity to one vendor.
         *
         *     Only executable auth modes belong here. OAuth1 and OAuth1a are unsupported.
         * @enum {string}
         */
        VendorAuthKind: "no_auth" | "api_key" | "basic" | "oauth2";
        /**
         * VoiceAudioTrackKind
         * @description Audio track associated with a segment.
         * @enum {string}
         */
        VoiceAudioTrackKind: "user" | "assistant" | "combined";
        /**
         * VoiceCanonicalState
         * @description Outcome of destructive post-call canonical history processing.
         * @enum {string}
         */
        VoiceCanonicalState: "not_run" | "clean" | "redacted" | "failed" | "no_storage";
        /** VoiceConfig */
        "VoiceConfig-Input": {
            /** Stt Provider Config Id */
            stt_provider_config_id?: string | null;
            /** Stt Provider Config Revision */
            stt_provider_config_revision?: number | null;
            /** Tts Provider Config Id */
            tts_provider_config_id?: string | null;
            /** Tts Provider Config Revision */
            tts_provider_config_revision?: number | null;
            /** Realtime Provider Config Id */
            realtime_provider_config_id?: string | null;
            /** Realtime Provider Config Revision */
            realtime_provider_config_revision?: number | null;
            /** Storage Provider Config Id */
            storage_provider_config_id?: string | null;
            /** Storage Provider Config Revision */
            storage_provider_config_revision?: number | null;
            conversation_control?: components["schemas"]["ConversationControl"];
            start_speaking_plan?: components["schemas"]["StartSpeakingPlan"];
            stop_speaking_plan?: components["schemas"]["StopSpeakingPlan"];
            silence?: components["schemas"]["SilenceConfig"];
            backchannel?: components["schemas"]["BackchannelConfig"];
            compliance?: components["schemas"]["CompliancePlan"];
            artifacts?: components["schemas"]["ArtifactPlan"];
            observability?: components["schemas"]["ObservabilityPlan"];
            background_audio?: components["schemas"]["BackgroundAudioConfig"];
            transport?: components["schemas"]["TransportConfig"];
            /** Hooks */
            hooks?: components["schemas"]["HookConfig"][];
            server?: components["schemas"]["ServerConfig"];
            fallback_chains?: components["schemas"]["FallbackChainsConfig"];
            capabilities?: components["schemas"]["VoiceRuntimeCapabilities"] | null;
            /**
             * Schema Version
             * @default voice-agent-config.v1
             */
            schema_version: string;
        };
        /** VoiceConfig */
        "VoiceConfig-Output": {
            /** Stt Provider Config Id */
            stt_provider_config_id?: string | null;
            /** Stt Provider Config Revision */
            stt_provider_config_revision?: number | null;
            /** Tts Provider Config Id */
            tts_provider_config_id?: string | null;
            /** Tts Provider Config Revision */
            tts_provider_config_revision?: number | null;
            /** Realtime Provider Config Id */
            realtime_provider_config_id?: string | null;
            /** Realtime Provider Config Revision */
            realtime_provider_config_revision?: number | null;
            /** Storage Provider Config Id */
            storage_provider_config_id?: string | null;
            /** Storage Provider Config Revision */
            storage_provider_config_revision?: number | null;
            conversation_control?: components["schemas"]["ConversationControl"];
            start_speaking_plan?: components["schemas"]["StartSpeakingPlan"];
            stop_speaking_plan?: components["schemas"]["StopSpeakingPlan"];
            silence?: components["schemas"]["SilenceConfig"];
            backchannel?: components["schemas"]["BackchannelConfig"];
            compliance?: components["schemas"]["CompliancePlan"];
            artifacts?: components["schemas"]["ArtifactPlan"];
            observability?: components["schemas"]["ObservabilityPlan"];
            background_audio?: components["schemas"]["BackgroundAudioConfig"];
            transport?: components["schemas"]["TransportConfig"];
            /** Hooks */
            hooks?: components["schemas"]["HookConfig"][];
            server?: components["schemas"]["ServerConfig"];
            fallback_chains?: components["schemas"]["FallbackChainsConfig"];
            capabilities?: components["schemas"]["VoiceRuntimeCapabilities"] | null;
            /**
             * Schema Version
             * @default voice-agent-config.v1
             */
            schema_version: string;
        };
        /**
         * VoiceConfigCompatibilityRead
         * @description Provider/platform capability separation for one Voice Config.
         */
        VoiceConfigCompatibilityRead: {
            /**
             * Voice Config Id
             * Format: uuid
             */
            voice_config_id: string;
            /** Voice Config Revision */
            voice_config_revision: number;
            /** Platform Features */
            platform_features: components["schemas"]["VoicePlatformFeatureRead"][];
            /** Selected Providers */
            selected_providers: components["schemas"]["VoiceProviderCapabilityRead"][];
            /** Guidance */
            guidance: string;
        };
        /** VoiceConfigCreate */
        VoiceConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /**
         * VoiceConfigRead
         * @description Current editable Voice Config definition.
         */
        VoiceConfigRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Name */
            name: string;
            /** Description */
            description: string | null;
            /** Revision */
            revision: number;
            config: components["schemas"]["VoiceConfig-Output"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** VoiceConfigResponse */
        VoiceConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Kind */
            kind: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** VoiceConfigUpdate */
        VoiceConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** VoiceConfigVerificationResponse */
        VoiceConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Kind */
            kind: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /**
         * VoicePlatformFeatureRead
         * @description One provider-independent behavior implemented by Eylo's voice pipeline.
         */
        VoicePlatformFeatureRead: {
            /** Key */
            key: string;
            /** Label */
            label: string;
            /** Enabled */
            enabled: boolean;
            /** Description */
            description: string;
            /**
             * Provider Independent
             * @default true
             * @constant
             */
            provider_independent: true;
        };
        /**
         * VoiceProviderCapabilityRead
         * @description Native behavior declared by one selected provider adapter.
         */
        VoiceProviderCapabilityRead: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "stt" | "tts" | "realtime";
            /**
             * Provider Config Id
             * Format: uuid
             */
            provider_config_id: string;
            /** Provider */
            provider: string;
            /** Ready */
            ready: boolean;
            /** Native Capabilities */
            native_capabilities: {
                [key: string]: unknown;
            };
        };
        /** VoiceRecordingResponse */
        VoiceRecordingResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /** Session Id */
            session_id: string;
            /**
             * Voice Session Id
             * Format: uuid
             */
            voice_session_id: string;
            /** Telephony Call Id */
            telephony_call_id?: string | null;
            /** User Audio Url */
            user_audio_url?: string | null;
            /** Agent Audio Url */
            agent_audio_url?: string | null;
            /** User Duration Seconds */
            user_duration_seconds?: number | null;
            /** Agent Duration Seconds */
            agent_duration_seconds?: number | null;
            /** User Sample Rate */
            user_sample_rate?: number | null;
            /** Agent Sample Rate */
            agent_sample_rate?: number | null;
            /** Upload State */
            upload_state: string;
            /** Upload Error */
            upload_error?: string | null;
            /** Created At */
            created_at: string;
        };
        /** VoiceRuntimeCapabilities */
        VoiceRuntimeCapabilities: {
            /** Warnings */
            warnings?: components["schemas"]["CapabilityWarning"][];
        };
        /**
         * VoiceRuntimeMode
         * @description Supported voice runtime modes.
         * @enum {string}
         */
        VoiceRuntimeMode: "browser_decomposed" | "browser_realtime" | "telephony";
        /** VoiceSegmentResponse */
        VoiceSegmentResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Voicesessionid
             * Format: uuid
             */
            voiceSessionId: string;
            /** Conversationid */
            conversationId?: string | null;
            /** Messageid */
            messageId?: string | null;
            /** Sequence */
            sequence: number;
            role: components["schemas"]["VoiceSegmentRole"];
            segmentType: components["schemas"]["VoiceSegmentType"];
            source: components["schemas"]["VoiceSegmentSource"];
            speechOutcome?: components["schemas"]["VoiceSpeechOutcome"] | null;
            /** Text */
            text?: string | null;
            /**
             * Ispartial
             * @default false
             */
            isPartial: boolean;
            /** Language */
            language?: string | null;
            /** Confidence */
            confidence?: number | null;
            /** Words */
            words?: {
                [key: string]: unknown;
            }[] | null;
            /** Startedatms */
            startedAtMs?: number | null;
            /** Endedatms */
            endedAtMs?: number | null;
            /** Durationms */
            durationMs?: number | null;
            audioTrack?: components["schemas"]["VoiceAudioTrackKind"] | null;
            /** Toolname */
            toolName?: string | null;
            /** Toolcallid */
            toolCallId?: string | null;
            /** Toolinput */
            toolInput?: {
                [key: string]: unknown;
            } | null;
            /** Tooloutput */
            toolOutput?: {
                [key: string]: unknown;
            } | null;
            /** Dtmfdigits */
            dtmfDigits?: string | null;
            /** Redactionstate */
            redactionState: string;
            /** Sourcecreatedat */
            sourceCreatedAt?: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
        };
        /**
         * VoiceSegmentRole
         * @description Speaker or actor represented by a timeline segment.
         * @enum {string}
         */
        VoiceSegmentRole: "user" | "assistant" | "tool" | "system";
        /**
         * VoiceSegmentSource
         * @description Subsystem that produced a voice transcript segment.
         * @enum {string}
         */
        VoiceSegmentSource: "stt" | "tts" | "realtime" | "telephony" | "tool" | "system" | "message";
        /**
         * VoiceSegmentType
         * @description Kinds of timeline entries in a voice transcript.
         * @enum {string}
         */
        VoiceSegmentType: "speech" | "tool_call" | "tool_result" | "event" | "silence";
        /** VoiceSessionDetail */
        VoiceSessionDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /**
             * Conversationid
             * Format: uuid
             */
            conversationId: string;
            /** Agentid */
            agentId?: string | null;
            /** Agentrevision */
            agentRevision?: number | null;
            /** Sessionid */
            sessionId: string;
            runtimeMode: components["schemas"]["VoiceRuntimeMode"];
            /** Transport */
            transport: string;
            status: components["schemas"]["VoiceSessionStatus"];
            canonicalState: components["schemas"]["VoiceCanonicalState"];
            /** Canonicalredactionversion */
            canonicalRedactionVersion?: number | null;
            /** Canonicalfailurecode */
            canonicalFailureCode?: string | null;
            /** Canonicalsourcecomplete */
            canonicalSourceComplete?: boolean | null;
            /** Canonicalprojectedat */
            canonicalProjectedAt?: string | null;
            /**
             * Canonicalmessagecount
             * @default 0
             */
            canonicalMessageCount: number;
            /**
             * Startedat
             * Format: date-time
             */
            startedAt: string;
            /** Endedat */
            endedAt?: string | null;
            /** Endedreason */
            endedReason?: string | null;
            /** Durationms */
            durationMs?: number | null;
            /**
             * Segmentcount
             * @default 0
             */
            segmentCount: number;
            /** Usertalktimems */
            userTalkTimeMs?: number | null;
            /** Assistanttalktimems */
            assistantTalkTimeMs?: number | null;
            /** Sttvendor */
            sttVendor?: string | null;
            /** Sttmodel */
            sttModel?: string | null;
            /** Ttsvendor */
            ttsVendor?: string | null;
            /** Ttsmodel */
            ttsModel?: string | null;
            /** Ttsvoice */
            ttsVoice?: string | null;
            /** Realtimevendor */
            realtimeVendor?: string | null;
            /** Realtimemodel */
            realtimeModel?: string | null;
            /** Telephonyprovider */
            telephonyProvider?: string | null;
            /** Fromnumber */
            fromNumber?: string | null;
            /** Tonumber */
            toNumber?: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Useraudiourl */
            userAudioUrl?: string | null;
            /** Assistantaudiourl */
            assistantAudioUrl?: string | null;
            /** Combinedaudiourl */
            combinedAudioUrl?: string | null;
            audioUrls?: components["schemas"]["VoiceTranscriptAudioUrls"];
            /** Segments */
            segments?: components["schemas"]["VoiceSegmentResponse"][];
            /**
             * Segmenttotal
             * @default 0
             */
            segmentTotal: number;
            /**
             * Segmentpage
             * @default 1
             */
            segmentPage: number;
            /**
             * Segmentlimit
             * @default 100
             */
            segmentLimit: number;
            /**
             * Segmentshasmore
             * @default false
             */
            segmentsHasMore: boolean;
            /** Metrics */
            metrics?: {
                [key: string]: unknown;
            } | null;
            /** Meta */
            meta?: {
                [key: string]: unknown;
            } | null;
        };
        /** VoiceSessionListResponse */
        VoiceSessionListResponse: {
            /** Data */
            data: components["schemas"]["VoiceSessionSummary"][];
            /** Total */
            total: number;
            /** Page */
            page: number;
            /** Limit */
            limit: number;
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean;
        };
        /**
         * VoiceSessionStatus
         * @description Lifecycle states for a durable voice transcript session.
         * @enum {string}
         */
        VoiceSessionStatus: "active" | "completed" | "failed";
        /** VoiceSessionSummary */
        VoiceSessionSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /**
             * Conversationid
             * Format: uuid
             */
            conversationId: string;
            /** Agentid */
            agentId?: string | null;
            /** Agentrevision */
            agentRevision?: number | null;
            /** Sessionid */
            sessionId: string;
            runtimeMode: components["schemas"]["VoiceRuntimeMode"];
            /** Transport */
            transport: string;
            status: components["schemas"]["VoiceSessionStatus"];
            canonicalState: components["schemas"]["VoiceCanonicalState"];
            /** Canonicalredactionversion */
            canonicalRedactionVersion?: number | null;
            /** Canonicalfailurecode */
            canonicalFailureCode?: string | null;
            /** Canonicalsourcecomplete */
            canonicalSourceComplete?: boolean | null;
            /** Canonicalprojectedat */
            canonicalProjectedAt?: string | null;
            /**
             * Canonicalmessagecount
             * @default 0
             */
            canonicalMessageCount: number;
            /**
             * Startedat
             * Format: date-time
             */
            startedAt: string;
            /** Endedat */
            endedAt?: string | null;
            /** Endedreason */
            endedReason?: string | null;
            /** Durationms */
            durationMs?: number | null;
            /**
             * Segmentcount
             * @default 0
             */
            segmentCount: number;
            /** Usertalktimems */
            userTalkTimeMs?: number | null;
            /** Assistanttalktimems */
            assistantTalkTimeMs?: number | null;
            /** Sttvendor */
            sttVendor?: string | null;
            /** Sttmodel */
            sttModel?: string | null;
            /** Ttsvendor */
            ttsVendor?: string | null;
            /** Ttsmodel */
            ttsModel?: string | null;
            /** Ttsvoice */
            ttsVoice?: string | null;
            /** Realtimevendor */
            realtimeVendor?: string | null;
            /** Realtimemodel */
            realtimeModel?: string | null;
            /** Telephonyprovider */
            telephonyProvider?: string | null;
            /** Fromnumber */
            fromNumber?: string | null;
            /** Tonumber */
            toNumber?: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
        };
        /**
         * VoiceSpeechOutcome
         * @description Eylo-owned terminal result for one assistant speech turn.
         * @enum {string}
         */
        VoiceSpeechOutcome: "drained" | "interrupted" | "failed" | "cancelled";
        /** VoiceTranscriptAudioUrls */
        VoiceTranscriptAudioUrls: {
            /** User */
            user?: string | null;
            /** Assistant */
            assistant?: string | null;
            /** Combined */
            combined?: string | null;
        };
        /** WaitlistRequestSchema */
        WaitlistRequestSchema: {
            /**
             * Email
             * Format: email
             * @description Member's email address
             */
            email: string;
        };
        /** WebRTCConfigCreate */
        WebRTCConfigCreate: {
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
        };
        /** WebRTCConfigResponse */
        WebRTCConfigResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Provider */
            provider: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Enabled */
            enabled: boolean;
            /** Configured */
            configured: boolean;
            /** Verified */
            verified: boolean;
            /** Ready */
            ready: boolean;
            /** Verifiedat */
            verifiedAt: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Secrets */
            secrets: {
                [key: string]: string;
            };
        };
        /** WebRTCConfigUpdate */
        WebRTCConfigUpdate: {
            /** Name */
            name?: string | null;
            /** Config */
            config?: {
                [key: string]: unknown;
            } | null;
            /** Secrets */
            secrets?: {
                [key: string]: string | null;
            } | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** WebRTCConfigVerificationResponse */
        WebRTCConfigVerificationResponse: {
            /**
             * Verified
             * @default true
             */
            verified: boolean;
            /** Provider */
            provider: string;
            /** Revision */
            revision: number;
            /**
             * Verifiedat
             * Format: date-time
             */
            verifiedAt: string;
        };
        /**
         * WidgetAgentCuratedCapabilitiesSchema
         * @description Curated capability groups belonging to one published Agent revision.
         */
        WidgetAgentCuratedCapabilitiesSchema: {
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Integrations */
            integrations: components["schemas"]["WidgetCuratedToolGroupSchema"][];
        };
        /**
         * WidgetConnectCredentialRequestSchema
         * @description End-user credential entry; ownership always comes from the widget session.
         */
        WidgetConnectCredentialRequestSchema: {
            /** Apikey */
            apiKey?: string | null;
            /** Username */
            username?: string | null;
            /** Password */
            password?: string | null;
        };
        /**
         * WidgetCuratedCapabilitiesRequestSchema
         * @description Published Agents whose curated capabilities the widget will render.
         */
        WidgetCuratedCapabilitiesRequestSchema: {
            /** Agentids */
            agentIds: string[];
        };
        /**
         * WidgetCuratedIntegrationSchema
         * @description Installed vendor plus connection state for the current contact.
         */
        WidgetCuratedIntegrationSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description: string;
            authKind: components["schemas"]["VendorAuthKind"];
            /** Connectionkind */
            connectionKind: string;
            /** Hasactiveconnection */
            hasActiveConnection: boolean;
            /**
             * Source
             * @default curated
             */
            source: string;
            /** Vendor */
            vendor: string;
        };
        /**
         * WidgetCuratedToolGroupSchema
         * @description Curated tools grouped by the vendor that authorizes them.
         */
        WidgetCuratedToolGroupSchema: {
            integration: components["schemas"]["WidgetCuratedIntegrationSchema"];
            /** Tools */
            tools: components["schemas"]["WidgetCuratedToolSchema"][];
        };
        /**
         * WidgetCuratedToolSchema
         * @description Safe curated tool metadata shown to an end user.
         */
        WidgetCuratedToolSchema: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description: string;
            /**
             * Kind
             * @default CURATED
             */
            kind: string;
        };
        /**
         * WidgetDevelopmentSessionResponse
         * @description Normal contact session issued to the standalone local widget.
         */
        WidgetDevelopmentSessionResponse: {
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /**
             * Contactid
             * Format: uuid
             */
            contactId: string;
            /** Sessiontoken */
            sessionToken: string;
            /**
             * Sessionexpiresat
             * Format: date-time
             */
            sessionExpiresAt: string;
        };
        /** WidgetInvitationExchangeRequest */
        WidgetInvitationExchangeRequest: {
            /** Token */
            token: string;
            /**
             * Requestid
             * Format: uuid
             */
            requestId: string;
        };
        /** WidgetInvitationExchangeResponse */
        WidgetInvitationExchangeResponse: {
            /**
             * Organizationid
             * Format: uuid
             */
            organizationId: string;
            /**
             * Contactid
             * Format: uuid
             */
            contactId: string;
            /**
             * Conversationid
             * Format: uuid
             */
            conversationId: string;
            /** Sessiontoken */
            sessionToken: string;
            /**
             * Sessionexpiresat
             * Format: date-time
             */
            sessionExpiresAt: string;
        };
        /**
         * WidgetInvitationIssueRequest
         * @description Identify one visitor and pin one published conversational agent.
         */
        WidgetInvitationIssueRequest: {
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Externalid */
            externalId?: string | null;
            /** Primaryemail */
            primaryEmail?: string | null;
            /** Primaryphone */
            primaryPhone?: string | null;
            /** Name */
            name?: string | null;
            /** Opener */
            opener: string;
            /**
             * Expiresat
             * Format: date-time
             */
            expiresAt: string;
        };
        /** WidgetInvitationIssueResponse */
        WidgetInvitationIssueResponse: {
            /**
             * Invitationid
             * Format: uuid
             */
            invitationId: string;
            /**
             * Contactid
             * Format: uuid
             */
            contactId: string;
            /**
             * Agentid
             * Format: uuid
             */
            agentId: string;
            /** Agentrevision */
            agentRevision: number;
            /**
             * Expiresat
             * Format: date-time
             */
            expiresAt: string;
            /** Invitationurl */
            invitationUrl: string;
            /** Warningcodes */
            warningCodes?: string[];
        };
        /**
         * WidgetKnowledgeIngestionRead
         * @description Narrow public receipt for one conversation file ingestion.
         */
        WidgetKnowledgeIngestionRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            state: components["schemas"]["DurableState"];
            /** Title */
            title: string | null;
            /** Source Uri */
            source_uri: string | null;
            /** Last Error */
            last_error: string | null;
        };
        /**
         * WidgetKnowledgeUploadCapabilityRead
         * @description Whether the pinned Agent revision accepts conversation file uploads.
         */
        WidgetKnowledgeUploadCapabilityRead: {
            /** Allowed */
            allowed: boolean;
        };
        /**
         * WidgetMessageContent
         * @description Content structure for ASSISTANT widget messages (single or compound).
         *
         *     Both single-component and compound payloads use contentKind=WIDGET.
         *     The widget SDK detects the format by checking for `component` (single)
         *     vs `components`+`root` (compound) keys in the payload.
         */
        WidgetMessageContent: {
            /**
             * Role
             * @default assistant
             * @constant
             */
            role: "assistant";
            /**
             * Content
             * @description Widget payload — single component or compound layout
             */
            content: components["schemas"]["WidgetPayload"] | components["schemas"]["CompoundWidgetPayload"];
        };
        /**
         * WidgetPayload
         * @description Validated single-component widget payload envelope.
         */
        WidgetPayload: {
            /**
             * Component
             * @description Registered widget component type
             */
            component: string;
            /**
             * Props
             * @description Component props validated by the backend
             */
            props?: {
                [key: string]: unknown;
            };
        };
        /**
         * WidgetResponseData
         * @description Structured widget submission payload from the user.
         */
        WidgetResponseData: {
            /**
             * Type
             * @default widget_response
             * @constant
             */
            type: "widget_response";
            /**
             * Widget Message Id
             * @description ID of the widget message this response belongs to
             */
            widget_message_id: string;
            /**
             * Component
             * @description Component type that emitted the response
             */
            component: string;
            /**
             * Action
             * @description Interaction verb such as submit or select
             */
            action?: string | null;
            /**
             * Data
             * @description Structured widget submission data
             */
            data?: {
                [key: string]: unknown;
            };
        };
        /**
         * WidgetResponseMessageContent
         * @description Content structure for USER widget response messages.
         */
        WidgetResponseMessageContent: {
            /**
             * Role
             * @default user
             * @constant
             */
            role: "user";
            /** @description Structured widget response */
            content: components["schemas"]["WidgetResponseData"];
        };
        /**
         * ToolExecutionMode
         * @description Operator policy on one installed tool, enforced before dispatch.
         * @enum {string}
         */
        eylo__modules__integrations_v2__domain__enums__ToolExecutionMode: "auto" | "requires_approval" | "disabled";
        /**
         * ToolExecutionMode
         * @description Persisted policy controlling whether an exact tool may execute.
         * @enum {string}
         */
        eylo__modules__tools__models__ToolExecutionMode: "auto" | "requires_approval" | "disabled";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_agents_api__organization_id__agents_get: {
        parameters: {
            query?: {
                agent_ids?: string[] | null;
                search?: string | null;
                status?: components["schemas"]["AgentStatus"][] | null;
                kind?: components["schemas"]["AgentKind"][] | null;
                sort_by?: components["schemas"]["AgentSortField"];
                sort_direction?: components["schemas"]["AgentSortDirection"];
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_agent_api__organization_id__agents_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentCreateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_agent_api__organization_id__agents__agent_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_agent_api__organization_id__agents__agent_id__put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentUpdateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    deactivate_agent_route_api__organization_id__agents__agent_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_agent_route_api__organization_id__agents__agent_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentUpdateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_effective_voice_stack_api__organization_id__agents__agent_id__effective_voice_stack_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentEffectiveVoiceStackResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agent_tools_api__organization_id__agents__agent_id__tools_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentToolsResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    assign_tool_to_agent_api__organization_id__agents__agent_id__tools_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentToolRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentToolInDb"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_tool_from_agent_api__organization_id__agents__agent_id__tools__tool_id__delete: {
        parameters: {
            query: {
                expected_draft_version: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publish_agent_api__organization_id__agents__agent_id__publish_put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentPublishRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    withdraw_agent_api__organization_id__agents__agent_id__unpublish_put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_agent_revision_api__organization_id__agents__agent_id__revisions_revoke_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentRevokeRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_budget_api__organization_id__agent_runs_budget_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrganizationExecutionBudgetRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_budget_api__organization_id__agent_runs_budget_put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrganizationExecutionBudgetUpsert"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrganizationExecutionBudgetRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_all_api__organization_id__agent_runs_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentRunRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_api__organization_id__agent_runs__run_id__cancel_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentRunCancelRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentRunCancellationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    answer_api__organization_id__agent_runs__run_id__input_requests__request_id__response_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                run_id: string;
                request_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentInputResponseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentInputRequestRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_one_api__organization_id__agent_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentRunRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_background_agents_api__organization_id__agents__agent_id__background_agents_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentBackgroundAgentInDb"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    attach_background_agent_api__organization_id__agents__agent_id__background_agents_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentBackgroundAgentCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentBackgroundAgentInDb"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    detach_background_agent_api__organization_id__agents__agent_id__background_agents__background_agent_id__delete: {
        parameters: {
            query: {
                expected_draft_version: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
                background_agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_background_agent_enabled_api__organization_id__agents__agent_id__background_agents__background_agent_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
                background_agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentBackgroundAgentUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentBackgroundAgentInDb"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_mcp_servers_api__organization_id__mcp_servers_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    register_mcp_server_api__organization_id__mcp_servers_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MCPServerCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discover_mcp_tools_api__organization_id__mcp_servers__server_id__discover_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                server_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_mcp_server_api__organization_id__mcp_servers__server_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                server_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MCPServerPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    withdraw_mcp_server_api__organization_id__mcp_servers__server_id__withdraw_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                server_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_mcp_server_revision_api__organization_id__mcp_servers__server_id__revisions__revision__revoke_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                server_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MCPServerRevoke"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_embedding_configs_api_embedding_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmbeddingConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_embedding_config_api_embedding_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmbeddingConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmbeddingConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_embedding_config_api_embedding_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmbeddingConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_embedding_config_api_embedding_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_embedding_config_api_embedding_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmbeddingConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmbeddingConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_embedding_config_api_embedding_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmbeddingConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_reranking_configs_api_reranking_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RerankingConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_reranking_config_api_reranking_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RerankingConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RerankingConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_reranking_config_api_reranking_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RerankingConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_reranking_config_api_reranking_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_reranking_config_api_reranking_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RerankingConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RerankingConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_reranking_config_api_reranking_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RerankingConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sandbox_configs_api_sandbox_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_sandbox_config_api_sandbox_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SandboxConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_sandbox_config_api_sandbox_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_sandbox_config_api_sandbox_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_sandbox_config_api_sandbox_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SandboxConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_sandbox_config_api_sandbox_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_objectives_api__organization_id__objectives_get: {
        parameters: {
            query?: {
                agent_id?: string | null;
                lifecycle?: components["schemas"]["AgentRunLifecycle"] | null;
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentRunRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_objective_api__organization_id__objectives_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ObjectiveCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentRunRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_objective_api__organization_id__objectives__objective_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                objective_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentRunRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_objective_api__organization_id__objectives__objective_id__cancel_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                objective_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentRunRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sandbox_grants_api__organization_id__sandboxes_grants_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxGrantRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    grant_sandbox_api__organization_id__sandboxes_grants_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SandboxGrantCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxGrantRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_sandbox_api__organization_id__sandboxes_grants__agent_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sandboxes_api__organization_id__sandboxes_get: {
        parameters: {
            query?: {
                include_destroyed?: boolean;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxSessionRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_sandbox_api__organization_id__sandboxes__session_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SandboxSessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    destroy_sandbox_api__organization_id__sandboxes__session_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_memory_configs_api_memory_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_memory_config_api_memory_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MemoryConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_memory_config_api_memory_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_memory_config_api_memory_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_memory_config_api_memory_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MemoryConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_memory_config_api_memory_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_memory_reindex_status_api_memory_configs__config_id__reindex_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryReindexStatusRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reindex_memory_config_api_memory_configs__config_id__reindex_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryReindexJobRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_memories_api__organization_id__memories_get: {
        parameters: {
            query?: {
                level?: components["schemas"]["MemoryLevel"][] | null;
                status?: components["schemas"]["MemoryStatus"][] | null;
                integrity?: components["schemas"]["MemoryIntegrityState"][] | null;
                recalled?: boolean | null;
                query?: string | null;
                sort?: components["schemas"]["MemorySort"];
                direction?: components["schemas"]["SortDirection"];
                limit?: number;
                offset?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryListRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_memory_api__organization_id__memories__memory_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                memory_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryDetailRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_actions_api__organization_id__schedules_actions_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_all_api__organization_id__schedules_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_api__organization_id__schedules_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_one_api__organization_id__schedules__schedule_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_api__organization_id__schedules__schedule_id__put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_api__organization_id__schedules__schedule_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_runs_api__organization_id__schedules__schedule_id__runs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleRunRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_revision_api__organization_id__schedules__schedule_id__revisions__revision__revoke_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                schedule_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleRevisionRevoke"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_knowledgebases_api__organization_id__knowledgebases_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgebaseRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_knowledgebase_api__organization_id__knowledgebases_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgebaseCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgebaseRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgebaseRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgebaseUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgebaseRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_knowledgebase_reindex_status_api__organization_id__knowledgebases__knowledgebase_id__reindex_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeReindexStatusRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reindex_knowledgebase_api__organization_id__knowledgebases__knowledgebase_id__reindex_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgebaseReindexRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeReindexJobRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    grant_knowledgebase_api__organization_id__knowledgebases_grants_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrantCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrantRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_grants_api__organization_id__knowledgebases_grants__agent_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrantRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_knowledgebase_api__organization_id__knowledgebases_grants__agent_id___knowledgebase_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_ingestions_api__organization_id__knowledgebases__knowledgebase_id__ingestions_get: {
        parameters: {
            query?: {
                state?: components["schemas"]["DurableState"] | null;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IngestionJobRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_ingestion_api__organization_id__knowledgebases__knowledgebase_id__ingestions_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IngestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IngestionJobRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_corpus_imports_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusImportRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_corpus_import_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorpusImportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusImportRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_corpus_import_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus__import_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
                import_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusImportRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_corpus_import_api__organization_id__knowledgebases__knowledgebase_id__ingestions_corpus__import_id__cancel_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
                import_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorpusImportRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_ingestion_api__organization_id__knowledgebases__knowledgebase_id__ingestions__job_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IngestionJobRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_ingestion_api__organization_id__knowledgebases__knowledgebase_id__ingestions__job_id__cancel_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                knowledgebase_id: string;
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IngestionJobRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    agent_stats_count_api__organization_id__agent_stats_count_get: {
        parameters: {
            query?: {
                status?: string[] | null;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": number;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_phone_numbers_api_phone_numbers_get: {
        parameters: {
            query?: {
                provider?: string | null;
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhoneNumbersPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_phone_number_api_phone_numbers_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PhoneNumberCreateSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhoneNumberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_phone_number_api_phone_numbers__phone_number_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                phone_number_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhoneNumberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_phone_number_api_phone_numbers__phone_number_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                phone_number_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhoneNumberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_phone_number_api_phone_numbers__phone_number_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                phone_number_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PhoneNumberUpdateSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhoneNumberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_calls_api_calls_get: {
        parameters: {
            query?: {
                /** @description Filter by call status */
                status?: string | null;
                /** @description Filter by call direction */
                direction?: string | null;
                /** @description Filter by campaign ID */
                campaignId?: string | null;
                /** @description Filter by conversation ID */
                conversationId?: string | null;
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TelephonyCallsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_call_api_calls__call_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                call_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TelephonyCallApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_call_api_calls__call_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                call_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeletionJobApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_templates_api_templates_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_template_api_templates_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_template_api_templates__template_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_template_draft_api_templates__template_id__draft_patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateDraftUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_template_api_templates__template_id__preview_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplatePreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateRenderResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publish_template_api_templates__template_id__publish_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplatePublishRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateRevisionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_template_revision_api_templates__template_id__revisions__revision__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateRevisionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    render_template_revision_api_templates__template_id__revisions__revision__render_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateRenderRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateRenderResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    withdraw_template_api_templates__template_id__withdraw_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_template_revision_api_templates__template_id__revisions__revision__revoke_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                template_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateRevokeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateRevisionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_telephony_configs_api_telephony_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderConfigApiResponseSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_telephony_config_api_telephony_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderConfigCreateSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderConfigApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_telephony_config_api_telephony_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderConfigApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_telephony_config_api_telephony_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_telephony_config_api_telephony_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderConfigUpdateSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderConfigApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_telephony_config_api_telephony_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_available_numbers_api_telephony_configs__provider_config_id__numbers_available_get: {
        parameters: {
            query: {
                /** @description ISO 3166-1 alpha-2 country code */
                country: string;
                numberType?: components["schemas"]["NumberType"];
                areaCode?: string | null;
                contains?: string | null;
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                provider_config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailableNumbersResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    purchase_number_api_telephony_configs__provider_config_id__numbers_purchase_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                provider_config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NumberPurchaseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhoneNumberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_event_health_api_events_health_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EventHealthResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_members_api__organization_id__members_get: {
        parameters: {
            query?: {
                search?: string | null;
                status?: components["schemas"]["MemberStatus"][] | null;
                sort_by?: components["schemas"]["MemberSortField"];
                sort_direction?: components["schemas"]["MemberSortDirection"];
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MembersPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_member_api__organization_id__members__member_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                member_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_user_sessions_api__organization_id__sessions_get: {
        parameters: {
            query?: {
                search?: string | null;
                contact_id?: string | null;
                state?: components["schemas"]["UserSessionState"][] | null;
                entry_channel?: components["schemas"]["UserSessionEntryChannel"][] | null;
                started_from?: string | null;
                started_to?: string | null;
                sort_by?: components["schemas"]["UserSessionSortField"];
                sort_direction?: components["schemas"]["UserSessionSortDirection"];
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserSessionPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_user_session_api__organization_id__sessions__user_session_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                user_session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserSessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_user_session_timeline_api__organization_id__sessions__user_session_id__timeline_get: {
        parameters: {
            query?: {
                category?: components["schemas"]["TimelineCategory"][] | null;
                event_type?: string[] | null;
                include_technical?: boolean;
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                user_session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserSessionTimelinePage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_curated_vendors_api__organization_id__curated_vendors_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CuratedVendorSummarySchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_curated_vendor_api__organization_id__curated_vendors__vendor__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                vendor: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CuratedVendorDetailSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    install_curated_vendor_api__organization_id__curated_vendors__vendor__install_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                vendor: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InstallVendorRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstallationSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_curated_installations_api__organization_id__curated_integrations_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstallationSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_curated_connection_aggregates_api__organization_id__aggregate_curated_connections_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionAggregateSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_curated_connections_api__organization_id__curated_connections_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_curated_connection_api__organization_id__curated_connections__connection_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_curated_vendor_tools_api__organization_id__curated_vendors__vendor__tools_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                vendor: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstalledToolSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_curated_tool_execution_mode_api__organization_id__curated_vendors__vendor__tools__tool_name__execution_mode_put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                vendor: string;
                tool_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetExecutionModeRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstalledToolSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    connect_curated_vendor_api__organization_id__curated_vendors__vendor__connect_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                vendor: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectCredentialRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    begin_curated_authorization_api__organization_id__curated_vendors__vendor__authorize_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                vendor: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BeginAuthorizationRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthorizationRedirectSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agent_curated_tools_api__organization_id__agents__agent_id__curated_tools_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstalledToolSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    replace_agent_curated_tools_api__organization_id__agents__agent_id__curated_tools_put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReplaceCuratedToolGrantsRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstalledToolSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    grant_agent_curated_tool_api__organization_id__agents__agent_id__curated_tools__vendor___tool_name__post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
                vendor: string;
                tool_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrantCuratedToolRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstalledToolSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_agent_curated_tool_api__organization_id__agents__agent_id__curated_tools__vendor___tool_name__delete: {
        parameters: {
            query: {
                expected_draft_version: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                agent_id: string;
                vendor: string;
                tool_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_llm_configs_api_llm_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LLMConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_llm_config_api_llm_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LLMConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LLMConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_llm_config_api_llm_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LLMConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_llm_config_api_llm_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_llm_config_api_llm_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LLMConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LLMConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_llm_config_api_llm_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LLMConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_capabilities_api_capabilities_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CapabilitiesResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_catalog_api_provider_onboarding_catalog_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOnboardingCatalogResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_system_tools_catalog_api__organization_id__tools_system_catalog_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolListResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_provider_tools_catalog_api__organization_id__tools_provider_catalog_get: {
        parameters: {
            query: {
                capability: components["schemas"]["Capability"];
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolListResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tools_api__organization_id__tools_get: {
        parameters: {
            query?: {
                mcp_server_id?: string | null;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolListResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_tool_api__organization_id__tools_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolCreateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_tool_api__organization_id__tools__tool_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_tool_api__organization_id__tools__tool_id__put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolUpdateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_tool_api__organization_id__tools__tool_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publish_tool_api__organization_id__tools__tool_id__publish_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolPublishRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolRevisionResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    withdraw_tool_api__organization_id__tools__tool_id__withdraw_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_tool_api__organization_id__tools__tool_id__revisions__revision__revoke_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                tool_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolRevokeRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolRevisionResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_aggregate_api__organization_id__aggregate_conversations__conversation_id__get: {
        parameters: {
            query?: {
                /** @description Include messages in response */
                include_messages?: boolean;
                /** @description Max messages to return */
                message_limit?: number;
                /** @description Include participants in response */
                include_participants?: boolean;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationAggregateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversations_aggregate_bulk_api__organization_id__aggregate_conversations_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConversationAggregateBulkRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationAggregateBulkResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_conversations_api__organization_id__conversations_get: {
        parameters: {
            query?: {
                conversationIds?: string[] | null;
                agentId?: string | null;
                q?: string | null;
                status?: components["schemas"]["ConversationStatus"][] | null;
                channel?: components["schemas"]["ConversationChannels"][] | null;
                sort?: components["schemas"]["ConversationSort"];
                direction?: components["schemas"]["ConversationSortDirection"];
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_api__organization_id__conversations__conversation_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_messages_api__organization_id__conversations__conversation_id__messages_get: {
        parameters: {
            query?: {
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationMessagesPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_participants_api__organization_id__conversations__conversation_id__participants_get: {
        parameters: {
            query?: {
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationParticipantsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_conversation_messages_api__organization_id__messages_get: {
        parameters: {
            query: {
                conversationIds: string[];
                agentId?: string | null;
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationMessagesPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_message_feedback_api__organization_id__messages_feedback_post: {
        parameters: {
            query: {
                request_id: string;
                feedback: components["schemas"]["MessageRequestFeedback"];
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_conversation_participants_api__organization_id__participants_get: {
        parameters: {
            query: {
                conversationIds: string[];
                agentId?: string | null;
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationParticipantsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_me_api_auth_me_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    issue_invitation_api__organization_id__widget_invitations_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WidgetInvitationIssueRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetInvitationIssueResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_api_keys_api_auth_api_keys_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiKeyInDb"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_api_key_api_auth_api_keys_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApiKeyCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiKeyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_api_key_api_auth_api_keys__api_key_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                api_key_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_contacts_api__organization_id__contacts_get: {
        parameters: {
            query?: {
                contact_ids?: string[] | null;
                search?: string | null;
                lifecycle?: components["schemas"]["ContactLifecycle"][] | null;
                sort_by?: components["schemas"]["ContactSortField"];
                sort_direction?: components["schemas"]["ContactSortDirection"];
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContactsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_contact_api__organization_id__contacts_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ContactCreateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContactApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_contact_api__organization_id__contacts__contact_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                contact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContactApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_contact_api__organization_id__contacts__contact_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                contact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeletionJobApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_contact_api__organization_id__contacts__contact_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                contact_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ContactPatchRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContactApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_deletion_job_api_deletions__job_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeletionJobApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversations_created_per_agent_api__organization_id__analytics_conversations_created_per_agent_get: {
        parameters: {
            query?: {
                startDate?: string | null;
                endDate?: string | null;
                timeslice?: ("day" | "week" | "month") | null;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown[];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_entity_created_api__organization_id__analytics__entity__created_get: {
        parameters: {
            query?: {
                startDate?: string | null;
                endDate?: string | null;
                timeslice?: ("day" | "week" | "month") | null;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                entity: "conversations" | "contacts" | "messages" | "members";
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown[];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_voice_configs_api__organization_id__voice_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_voice_config_api__organization_id__voice_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrganizationVoiceConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_voice_config_api__organization_id__voice_configs__voice_config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                voice_config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_voice_config_api__organization_id__voice_configs__voice_config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                voice_config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_voice_config_api__organization_id__voice_configs__voice_config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                voice_config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrganizationVoiceConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_voice_config_compatibility_api__organization_id__voice_configs__voice_config_id__compatibility_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                voice_config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigCompatibilityRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_voice_config_section_api__organization_id__voice_configs__voice_config_id__sections__section__patch: {
        parameters: {
            query: {
                expected_revision: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                voice_config_id: string;
                section: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                } | {
                    [key: string]: unknown;
                }[];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_stt_configs_api_stt_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_stt_config_api_stt_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoiceConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_stt_config_api_stt_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_stt_config_api_stt_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_stt_config_api_stt_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoiceConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_stt_config_api_stt_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tts_configs_api_tts_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_tts_config_api_tts_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoiceConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_tts_config_api_tts_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_tts_config_api_tts_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_tts_config_api_tts_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoiceConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_tts_config_api_tts_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_realtime_configs_api_realtime_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_realtime_config_api_realtime_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoiceConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_realtime_config_api_realtime_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_realtime_config_api_realtime_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_realtime_config_api_realtime_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoiceConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_realtime_config_api_realtime_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_webrtc_configs_api_webrtc_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WebRTCConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_webrtc_config_api_webrtc_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WebRTCConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WebRTCConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_webrtc_config_api_webrtc_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WebRTCConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_webrtc_config_api_webrtc_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_webrtc_config_api_webrtc_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WebRTCConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WebRTCConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_webrtc_config_api_webrtc_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WebRTCConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_email_configs_api_email_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmailConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_email_config_api_email_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmailConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmailConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_email_config_api_email_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmailConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_email_config_api_email_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_email_config_api_email_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmailConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmailConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_email_config_api_email_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmailConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_storage_configs_api_storage_configs_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorageConfigResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_storage_config_api_storage_configs_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StorageConfigCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorageConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_storage_config_api_storage_configs__config_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorageConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_storage_config_api_storage_configs__config_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_storage_config_api_storage_configs__config_id__patch: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StorageConfigUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorageConfigResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_storage_config_api_storage_configs__config_id__verify_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                config_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorageConfigVerificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_recordings_api_organizations__organization_id__conversations__conversation_id__recordings_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecordingListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_recording_track_api_organizations__organization_id__conversations__conversation_id__recordings__recording_id___track__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
                recording_id: string;
                track: "user" | "agent";
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "audio/wav": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_voice_sessions_api__organization_id__voice_sessions_get: {
        parameters: {
            query?: {
                page?: number;
                limit?: number;
                conversation_id?: string | null;
                agent_id?: string | null;
                status?: components["schemas"]["VoiceSessionStatus"] | null;
                runtime_mode?: components["schemas"]["VoiceRuntimeMode"] | null;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceSessionListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_voice_session_api__organization_id__voice_sessions__voice_session_id__get: {
        parameters: {
            query?: {
                segment_page?: number;
                segment_limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                voice_session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceSessionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_voice_session_for_conversation_api__organization_id__conversations__conversation_id__voice_session_get: {
        parameters: {
            query?: {
                segment_page?: number;
                segment_limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VoiceSessionDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_agent_swarm_api__organization_id__agent_swarm_create_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentSwarmCreateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agent_swarms_api__organization_id__agent_swarm_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmResponseSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_agent_swarm_api__organization_id__agent_swarm__swarm_id__put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentSwarmUpdateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_agent_swarm_api__organization_id__agent_swarm__swarm_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_agent_to_swarm_api__organization_id__agent_swarm__swarm_id__add_agent_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentSwarmMappingCreateRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmMappingResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agents_in_swarm_api__organization_id__agent_swarm__swarm_id__agents_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmMappingResponseSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publish_agent_swarm_api__organization_id__agent_swarm__swarm_id__publish_put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentSwarmPublishRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmRevisionResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    withdraw_agent_swarm_api__organization_id__agent_swarm__swarm_id__unpublish_put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_agent_swarm_revision_api__organization_id__agent_swarm__swarm_id__revisions_revoke_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentSwarmRevokeRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSwarmRevisionResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_agent_from_swarm_api__organization_id__agent_swarm__swarm_id__remove_agent_delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                swarm_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentSwarmMappingDeleteRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_campaigns_api__organization_id__campaigns_get: {
        parameters: {
            query?: {
                status?: string | null;
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_campaign_api__organization_id__campaigns_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CampaignCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_campaign_api__organization_id__campaigns__campaign_id__get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_campaign_api__organization_id__campaigns__campaign_id__put: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CampaignUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_campaign_api__organization_id__campaigns__campaign_id__delete: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_campaign_preparation_api__organization_id__campaigns__campaign_id__preparation_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignPreparationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_campaign_api__organization_id__campaigns__campaign_id__start_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pause_campaign_api__organization_id__campaigns__campaign_id__pause_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_campaign_api__organization_id__campaigns__campaign_id__cancel_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_campaign_revision_api__organization_id__campaigns__campaign_id__revisions__revision__revoke_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CampaignRevisionRevokeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_contacts_api__organization_id__campaigns__campaign_id__contacts_get: {
        parameters: {
            query?: {
                status?: string | null;
                /** @description Page number */
                page?: number;
                /** @description Items per page */
                limit?: number;
            };
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignContactsPaginated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_contacts_api__organization_id__campaigns__campaign_id__contacts_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CampaignContactsUploadRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    select_contacts_api__organization_id__campaigns__campaign_id__contacts_select_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CampaignContactsSelectRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_analytics_api__organization_id__campaigns__campaign_id__analytics_get: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                campaign_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CampaignAnalyticsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    outbound_call_api_voice_outbound_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    waitlist_api_auth_waitlist_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WaitlistRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    register_api_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegistrationRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    invite_member_api_auth_invite_post: {
        parameters: {
            query?: never;
            header?: {
                "X-API-Key"?: string | null;
                "X-Session-ID"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InviteMemberRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    accept_invite_api_auth_accept_invite_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AcceptInviteRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberApiResponseSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    forgot_password_api_auth_forgot_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ForgotPasswordRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_password_api_auth_reset_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResetPasswordRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    validate_session_api_public_session_validate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionValidationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionValidationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    exchange_invitation_api_public_widget_invitations_exchange_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WidgetInvitationExchangeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetInvitationExchangeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_development_session_api_public_widget_development_session_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetDevelopmentSessionResponse"];
                };
            };
        };
    };
    complete_curated_authorization_api_oauth_callback_get: {
        parameters: {
            query: {
                code?: string | null;
                state: string;
                error?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    status_callback_api_telephony_webhooks__provider__status_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider: "twilio" | "plivo" | "vonage" | "exotel";
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    widget_list_curated_capabilities_api_widget__organization_id__curated_connections_capabilities_get: {
        parameters: {
            query: {
                /** @description Published Agent shown by the widget. */
                agent_id: string;
            };
            header?: {
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetCuratedToolGroupSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    widget_list_bulk_curated_capabilities_api_widget__organization_id__curated_connections_bulk_capabilities_post: {
        parameters: {
            query?: never;
            header?: {
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WidgetCuratedCapabilitiesRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetAgentCuratedCapabilitiesSchema"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    widget_initiate_curated_oauth_api_widget__organization_id__curated_connections_oauth_initiate_get: {
        parameters: {
            query: {
                /** @description Curated vendor id. */
                vendor: string;
                /** @description Contact-owned conversation. */
                conversation_id: string;
            };
            header?: {
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthorizationRedirectSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    widget_connect_curated_credential_api_widget__organization_id__curated_connections__vendor__connect_post: {
        parameters: {
            query: {
                /** @description Contact-owned conversation. */
                conversation_id: string;
            };
            header?: {
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                vendor: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WidgetConnectCredentialRequestSchema"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionSchema"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_widget_knowledge_file_upload_capability_api_widget__organization_id__conversations__conversation_id__knowledgebases_file_upload_capability_get: {
        parameters: {
            query?: never;
            header: {
                "X-Eylo-User-Session-ID": string;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetKnowledgeUploadCapabilityRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_widget_knowledge_file_api_widget__organization_id__conversations__conversation_id__knowledgebases_files_post: {
        parameters: {
            query?: never;
            header: {
                "X-Eylo-Filename": string;
                "X-Eylo-User-Session-ID": string;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/octet-stream": string;
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetKnowledgeIngestionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_widget_knowledge_ingestion_api_widget__organization_id__conversations__conversation_id__knowledgebases_ingestions__job_id__get: {
        parameters: {
            query?: never;
            header: {
                "X-Eylo-User-Session-ID": string;
                "X-Session-ID"?: string | null;
            };
            path: {
                organization_id: string;
                conversation_id: string;
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WidgetKnowledgeIngestionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_root__get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    health_check_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
