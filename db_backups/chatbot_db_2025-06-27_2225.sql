--
-- PostgreSQL database dump
--

-- Dumped from database version 15.4 (Debian 15.4-2.pgdg120+1)
-- Dumped by pg_dump version 15.4 (Debian 15.4-2.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: langchain_pg_collection; Type: TABLE; Schema: public; Owner: user
--

CREATE TABLE public.langchain_pg_collection (
    name character varying,
    cmetadata json,
    uuid uuid NOT NULL
);


ALTER TABLE public.langchain_pg_collection OWNER TO "user";

--
-- Name: langchain_pg_embedding; Type: TABLE; Schema: public; Owner: user
--

CREATE TABLE public.langchain_pg_embedding (
    collection_id uuid,
    embedding public.vector,
    document character varying,
    cmetadata json,
    custom_id character varying,
    uuid uuid NOT NULL
);


ALTER TABLE public.langchain_pg_embedding OWNER TO "user";

--
-- Data for Name: langchain_pg_collection; Type: TABLE DATA; Schema: public; Owner: user
--

COPY public.langchain_pg_collection (name, cmetadata, uuid) FROM stdin;
chatbot_docs	null	27ed4609-dc12-4e09-ba64-1896289114aa
\.


--
-- Data for Name: langchain_pg_embedding; Type: TABLE DATA; Schema: public; Owner: user
--

COPY public.langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id, uuid) FROM stdin;
\.


--
-- Name: langchain_pg_collection langchain_pg_collection_pkey; Type: CONSTRAINT; Schema: public; Owner: user
--

ALTER TABLE ONLY public.langchain_pg_collection
    ADD CONSTRAINT langchain_pg_collection_pkey PRIMARY KEY (uuid);


--
-- Name: langchain_pg_embedding langchain_pg_embedding_pkey; Type: CONSTRAINT; Schema: public; Owner: user
--

ALTER TABLE ONLY public.langchain_pg_embedding
    ADD CONSTRAINT langchain_pg_embedding_pkey PRIMARY KEY (uuid);


--
-- Name: langchain_pg_embedding langchain_pg_embedding_collection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: user
--

ALTER TABLE ONLY public.langchain_pg_embedding
    ADD CONSTRAINT langchain_pg_embedding_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.langchain_pg_collection(uuid) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

