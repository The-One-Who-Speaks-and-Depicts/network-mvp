"""Entities pipeline tests."""

# Focused suites intentionally share realistic setup snippets.
# pylint: disable=duplicate-code

from tests.test_support import (
    CandidateEntity,
    CanonicalEntity,
    CooccurrenceEdge,
    CooccurrenceService,
    EntityExtractionService,
    EntityMergeService,
    FakeLlmClient,
    LemmatizedFile,
    LlmClientError,
    Path,
    SemanticEdge,
    SemanticRelationService,
    ScaffoldTestBase,
)


class EntityAndRelationTests(ScaffoldTestBase):
    def test_entity_extraction_parses_candidates_per_file(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша къ ѥсифъ",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(responses=["грикша\tгрикши\nѥсифъ\tѥсифу"])
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(
            lemmatized_files,
            source_text_by_file={"003.003.txt": "поклонъ ѿ грикши къ ѥсифу"},
        )

        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(isinstance(candidate, CandidateEntity) for candidate in candidates)
        )
        self.assertEqual(
            [candidate.file_id for candidate in candidates],
            ["text_0001", "text_0001"],
        )
        self.assertEqual(
            [candidate.filename for candidate in candidates],
            ["003.003.txt", "003.003.txt"],
        )
        self.assertEqual([candidate.name for candidate in candidates], ["грикша", "ѥсифъ"])
        self.assertEqual([candidate.evidence for candidate in candidates], ["грикши", "ѥсифу"])
        self.assertIn("поклонъ ѿ грикша", client.prompts[0])
        self.assertIn("поклонъ ѿ грикши", client.prompts[0])

    def test_entity_extraction_defaults_evidence_to_name(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(responses=["грикша"])
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(lemmatized_files)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "грикша")
        self.assertEqual(candidates[0].evidence, "грикша")

    def test_entity_extraction_skips_llm_failure(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(lemmatized_files)

        self.assertEqual(candidates, [])

    def test_entity_extraction_with_zenodo_birchbark_fixture(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша къ ѥсифъ къ федосьꙗ",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(responses=["грикша\tгрикши\nѥсифъ\tѥсифу\nфедосьꙗ\tфедосьӏ"])
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(lemmatized_files)

        self.assertEqual(
            [candidate.name for candidate in candidates],
            ["грикша", "ѥсифъ", "федосьꙗ"],
        )
        self.assertEqual(
            [candidate.evidence for candidate in candidates],
            ["грикши", "ѥсифу", "федосьӏ"],
        )
        self.assertEqual(
            [candidate.filename for candidate in candidates],
            ["003.003.txt", "003.003.txt", "003.003.txt"],
        )

    def test_entity_merge_groups_aliases_and_source_files(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Грикша",
                evidence="грикши",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="004.004.txt",
                name="грикша",
                evidence="грикша",
            ),
            CandidateEntity(
                file_id="text_0003",
                filename="005.005.txt",
                name="Ѥсифъ",
                evidence="ѥсифу",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)

        self.assertEqual(len(merged), 2)
        self.assertTrue(all(isinstance(entity, CanonicalEntity) for entity in merged))
        self.assertEqual(merged[0].canonical_name, "грикша")
        self.assertEqual(merged[0].aliases, ("Грикша", "грикша"))
        self.assertEqual(merged[0].source_files, ("003.003.txt", "004.004.txt"))
        self.assertEqual(merged[0].evidence, ("грикша", "грикши"))

    def test_entity_merge_strips_supported_titles(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="001.txt",
                name="княгиня Ольга",
                evidence="княгиня ольга",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="002.txt",
                name="Ольга",
                evidence="ольга",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].canonical_name, "ольга")
        self.assertEqual(merged[0].aliases, ("Ольга", "княгиня Ольга"))

    def test_entity_merge_infers_gender_when_possible(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="001.txt",
                name="N",
                evidence="n",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="002.txt",
                name="Ольга",
                evidence="ольга",
            ),
            CandidateEntity(
                file_id="text_0003",
                filename="003.txt",
                name="Ѥсифъ",
                evidence="ѥсифу",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)

        self.assertEqual(merged[0].gender_inference, "unresolved")
        self.assertEqual(merged[1].gender_inference, "female")
        self.assertEqual(merged[2].gender_inference, "not_inferred")

    def test_entity_merge_prefers_female_over_weaker_heuristics(self) -> None:
        merged = EntityMergeService().merge_candidates(
            [
                CandidateEntity(
                    file_id="text_0001",
                    filename="001.txt",
                    name="N",
                    evidence="n",
                ),
                CandidateEntity(
                    file_id="text_0002",
                    filename="002.txt",
                    name="Княгиня N",
                    evidence="княгиня n",
                ),
            ]
        )

        self.assertEqual(merged[0].gender_inference, "female")

    def test_entity_merge_can_delegate_gender_inference_to_llm(self) -> None:
        llm_client = FakeLlmClient(responses=["female"])
        merged = EntityMergeService(llm_client).merge_candidates(
            [
                CandidateEntity(
                    file_id="text_0001",
                    filename="001.txt",
                    name=(
                        "анна<tab>в лѣто 6519. преставися раба божиа анна, "
                        "цесарица володимиря."
                    ),
                    evidence=(
                        "анна<tab>в лѣто 6519. преставися раба божиа анна, "
                        "цесарица володимиря."
                    ),
                ),
            ]
        )

        self.assertEqual(merged[0].canonical_name, "анна")
        self.assertEqual(merged[0].gender_inference, "female")
        self.assertIn("цесарица володимиря", llm_client.prompts[0])

    def test_entity_merge_with_birchbark_style_candidates(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Грикша",
                evidence="грикши",
            ),
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Ѥсифъ",
                evidence="ѥсифу",
            ),
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Федосьꙗ",
                evidence="федосьӏ",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="004.004.txt",
                name="Петръ",
                evidence="петра",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="004.004.txt",
                name="Юрга",
                evidence="юрги",
            ),
            CandidateEntity(
                file_id="text_0003",
                filename="005.005.txt",
                name="княгиня Ольга",
                evidence="княгиня ольга",
            ),
            CandidateEntity(
                file_id="text_0004",
                filename="006.006.txt",
                name="Ольга",
                evidence="ольга",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)
        merged_by_name = {entity.canonical_name: entity for entity in merged}

        self.assertIn("грикша", merged_by_name)
        self.assertIn("ѥсифъ", merged_by_name)
        self.assertIn("федосьꙗ", merged_by_name)
        self.assertIn("петръ", merged_by_name)
        self.assertIn("юрга", merged_by_name)
        self.assertIn("ольга", merged_by_name)
        self.assertEqual(merged_by_name["грикша"].evidence, ("грикши",))
        self.assertEqual(merged_by_name["ѥсифъ"].source_files, ("003.003.txt",))
        self.assertEqual(merged_by_name["федосьꙗ"].gender_inference, "female")
        self.assertEqual(merged_by_name["ольга"].aliases, ("Ольга", "княгиня Ольга"))
        self.assertEqual(merged_by_name["ольга"].source_files, ("005.005.txt", "006.006.txt"))

    def test_cooccurrence_builds_weighted_edges(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="федосьꙗ",
                aliases=("Федосьꙗ",),
                source_files=("003.003.txt",),
                evidence=("федосьӏ",),
                gender_inference="female",
            ),
            CanonicalEntity(
                canonical_name="петръ",
                aliases=("Петръ",),
                source_files=("004.004.txt",),
                evidence=("петра",),
                gender_inference="not_inferred",
            ),
        ]
        edges = CooccurrenceService().build_edges(entities)

        self.assertTrue(all(isinstance(edge, CooccurrenceEdge) for edge in edges))
        self.assertEqual(
            [(edge.source, edge.target, edge.weight, edge.source_files) for edge in edges],
            [
                ("грикша", "петръ", 1, ("004.004.txt",)),
                ("грикша", "федосьꙗ", 1, ("003.003.txt",)),
                ("грикша", "ѥсифъ", 1, ("003.003.txt",)),
                ("федосьꙗ", "ѥсифъ", 1, ("003.003.txt",)),
            ],
        )

    def test_cooccurrence_avoids_self_loops(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша", "грикша"),
                source_files=("003.003.txt",),
                evidence=("грикши", "грикша"),
                gender_inference="not_inferred",
            )
        ]
        edges = CooccurrenceService().build_edges(entities)

        self.assertEqual(edges, [])

    def test_cooccurrence_with_birchbark_style_entities(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="федосьꙗ",
                aliases=("Федосьꙗ",),
                source_files=("003.003.txt",),
                evidence=("федосьӏ",),
                gender_inference="female",
            ),
            CanonicalEntity(
                canonical_name="петръ",
                aliases=("Петръ",),
                source_files=("004.004.txt",),
                evidence=("петра",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="юрга",
                aliases=("Юрга",),
                source_files=("004.004.txt",),
                evidence=("юрги",),
                gender_inference="female",
            ),
        ]
        edges = CooccurrenceService().build_edges(entities)
        edge_map = {(edge.source, edge.target): edge for edge in edges}

        self.assertEqual(edge_map[("грикша", "петръ")].source_files, ("004.004.txt",))
        self.assertEqual(edge_map[("грикша", "юрга")].source_files, ("004.004.txt",))
        self.assertEqual(edge_map[("грикша", "ѥсифъ")].source_files, ("003.003.txt",))
        self.assertEqual(edge_map[("федосьꙗ", "ѥсифъ")].weight, 1)
        self.assertEqual(edge_map[("петръ", "юрга")].weight, 1)

    def test_semantic_relation_annotation_disabled_keeps_plain_edges(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            )
        ]
        service = SemanticRelationService(FakeLlmClient())

        annotated = service.annotate_edges(edges, lemmatized_context_by_file={}, enabled=False)

        self.assertEqual(len(annotated), 1)
        self.assertIsInstance(annotated[0], SemanticEdge)
        self.assertEqual(annotated[0].semantic_relation, None)
        self.assertEqual(annotated[0].semantic_confidence, None)

    def test_semantic_relation_annotation_parses_allowed_label(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="княгиня ольга",
                target="игорь",
                weight=1,
                source_files=("001.txt",),
            )
        ]
        client = FakeLlmClient(responses=["wife of\tsource_to_target\t0.8"])
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={"001.txt": "ольга и игорь"},
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "wife of")
        self.assertEqual(annotated[0].semantic_direction, "source_to_target")
        self.assertEqual(annotated[0].semantic_confidence, 0.8)

    def test_semantic_relation_annotation_maps_unknown_label_to_not_stated(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            )
        ]
        client = FakeLlmClient(responses=["ally of\tsource_to_target\t0.7"])
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={"003.003.txt": "грикша и ѥсифъ"},
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "not stated")
        self.assertEqual(annotated[0].semantic_confidence, 0.0)

    def test_semantic_relation_annotation_rejects_unknown_direction(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            )
        ]
        client = FakeLlmClient(responses=["wife of\tleft_to_right\t0.7"])
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={"003.003.txt": "грикша и ѥсифъ"},
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "not stated")
        self.assertIsNone(annotated[0].semantic_direction)
        self.assertEqual(annotated[0].semantic_confidence, 0.0)

    def test_semantic_relation_annotation_falls_back_on_error(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            )
        ]
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={"003.003.txt": "грикша и ѥсифъ"},
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "not stated")
        self.assertEqual(annotated[0].semantic_confidence, 0.0)

    def test_semantic_relation_with_birchbark_style_context(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            ),
            CooccurrenceEdge(
                source="ѥсифъ",
                target="федосьꙗ",
                weight=1,
                source_files=("003.003.txt",),
            ),
        ]
        client = FakeLlmClient(
            responses=[
                "not stated\t\t0.3",
                "daughter of\ttarget_to_source\t0.6",
            ]
        )
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={
                "003.003.txt": "поклонъ ѿ грикша къ ѥсифъ ... къ федосьꙗ ...",
            },
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "not stated")
        self.assertEqual(annotated[1].semantic_relation, "daughter of")
        self.assertEqual(annotated[1].semantic_direction, "target_to_source")
        self.assertEqual(annotated[1].semantic_confidence, 0.6)
        self.assertIn("Entity A: грикша", client.prompts[0])
        self.assertIn("Entity B: ѥсифъ", client.prompts[0])
