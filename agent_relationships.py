@bp.route("/api/v2/relationships", methods=["GET"])
    def get_relationships_v2():
        agent_id, agent_error = _optional_string_field(request.args, "agent_id")
        if agent_error:
            return agent_error
        state, state_error = _optional_string_field(request.args, "state")
        if state_error:
            return state_error
        
        if state:
            try:
                RelationshipState(state)  # validate
            except ValueError:
                return jsonify({"error": "Invalid state"}), 400
        
        relationships = engine.get_all_relationships(agent_id=agent_id, state=state)
        return jsonify({"relationships": relationships})
    
    @bp.route("/api/v2/relationships/<agent_a>/<agent_b>", methods=["GET"])
    def get_relationship_v2(agent_a: str, agent_b: str):
        rel = engine.get_relationship(agent_a, agent_b)
        if not rel:
            return jsonify({"error": "Relationship not found"}), 404
        return jsonify(rel)
    
    @bp.route("/api/v2/relationships/<agent_a>/<agent_b>/disagree", methods=["POST"])
    def disagree_v2(agent_a: str, agent_b: str):
        auth_error = _require_mutation_admin()
        if auth_error:
            return auth_error

        data, json_error = _mutation_json_object()
        if json_error:
            return json_error
        topic, topic_error = _optional_string_field(data, "topic", "unspecified")
        if topic_error:
            return topic_error
        description, description_error = _optional_string_field(data, "description")
        if description_error:
            return description_error
        try:
            result = engine.record_disagreement(
                agent_a, agent_b,
                topic=topic,
                description=description or None,
            )
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400