--
-- PostgreSQL database dump
--

-- Dumped from database version 16.8
-- Dumped by pg_dump version 16.5

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: order; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public."order" (
    id integer NOT NULL,
    order_number character varying(20) NOT NULL,
    email character varying(120) NOT NULL,
    total_cost double precision NOT NULL,
    status character varying(20),
    created_at timestamp without time zone,
    invoice_number character varying(50),
    po_number character varying(50)
);


ALTER TABLE public."order" OWNER TO neondb_owner;

--
-- Name: order_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

CREATE SEQUENCE public.order_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.order_id_seq OWNER TO neondb_owner;

--
-- Name: order_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: neondb_owner
--

ALTER SEQUENCE public.order_id_seq OWNED BY public."order".id;


--
-- Name: order_item; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.order_item (
    id integer NOT NULL,
    order_id integer NOT NULL,
    file_key character varying(255) NOT NULL,
    width_inches double precision NOT NULL,
    height_inches double precision NOT NULL,
    quantity integer NOT NULL,
    cost double precision NOT NULL,
    notes text
);


ALTER TABLE public.order_item OWNER TO neondb_owner;

--
-- Name: order_item_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

CREATE SEQUENCE public.order_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.order_item_id_seq OWNER TO neondb_owner;

--
-- Name: order_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: neondb_owner
--

ALTER SEQUENCE public.order_item_id_seq OWNED BY public.order_item.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(64) NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(256),
    is_admin boolean DEFAULT false
);


ALTER TABLE public.users OWNER TO neondb_owner;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO neondb_owner;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: neondb_owner
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: order id; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public."order" ALTER COLUMN id SET DEFAULT nextval('public.order_id_seq'::regclass);


--
-- Name: order_item id; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.order_item ALTER COLUMN id SET DEFAULT nextval('public.order_item_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: order; Type: TABLE DATA; Schema: public; Owner: neondb_owner
--

COPY public."order" (id, order_number, email, total_cost, status, created_at, invoice_number, po_number) FROM stdin;
283	DTF-08944E59	kurt@arrowsp.net	0.3	completed	2025-02-21 17:40:59.623478	816953	LIONS - NAME SAMPLES
250	DTF-7D762B2F	kurt@arrowsp.net	86.4	completed	2025-02-17 21:59:20.39777	816953	HDZ CONSTRUCTION
247	DTF-A5F2929D	kurt@arrowsp.net	0.6	completed	2025-02-17 21:36:29.984118	816953	VALLEY VIEW BA
248	DTF-685FAE1E	kurt@arrowsp.net	10.700000000000001	completed	2025-02-17 21:39:43.064307	816953	GUILLEN ROOFING
245	DTF-8C34C95F	kurt@arrowsp.net	35.46	completed	2025-02-17 21:22:27.523582	816953	McCAULEY AUCTIONS; VALLEY VIEW BB; MARKED TREE
249	DTF-8B4F5212	capmanoffice@yahoo.com	200.68	completed	2025-02-17 21:58:07.946009	816954	021725
240	DTF-C29DC5EB	kurt@arrowsp.net	120	completed	2025-02-17 13:17:07.585466	816871	DELTA T - ARKANSAS CHARM
284	DTF-187394D5	capmanoffice@yahoo.com	7.999999999999999	completed	2025-02-21 21:54:38.462762	816954	022125OopsForgotThese
254	DTF-280ECB14	kurt@arrowsp.net	2	completed	2025-02-18 18:51:26.257578	816953	HAVOC SOFTBALL
243	DTF-3BD59F4D	kurt@arrowsp.net	0.16	completed	2025-02-17 13:42:20.983348	816871	NUCKLES & SON PLUMBING LEFT CHEST
242	DTF-ED0E8D22	kurt@arrowsp.net	88	completed	2025-02-17 13:29:04.746607	816871	DELTA T - CITIZEN OF HEAVEN
241	DTF-476DB723	kurt@arrowsp.net	105.60000000000001	completed	2025-02-17 13:23:18.553833	816871	DELTA T - NO LUCK JUST JESUS
239	DTF-47E20254	kurt@arrowsp.net	273.6	completed	2025-02-17 13:12:30.109653	816871	DELTA T - ARKANSAS MATCHBOX
238	DTF-9D658C2D	kurt@arrowsp.net	2.16	completed	2025-02-17 13:02:56.217387	816871	NUCKLES & SON PLUMBING
228	DTF-05A29259	kurt@arrowsp.net	0.9600000000000001	completed	2025-02-14 21:47:37.774036	816871	BROOKLAND SOCCER
269	DTF-9DD6A873	kurt@arrowsp.net	9.719999999999999	completed	2025-02-19 17:04:48.097334	816953	CAMP QUALITY
227	DTF-D4621032	capmanoffice@yahoo.com	183.84	completed	2025-02-14 19:35:45.385868	816872	021425
275	DTF-05F402C6	kurt@arrowsp.net	5.000000000000001	completed	2025-02-19 21:44:52.952112	816953	ENCOMPASS
276	DTF-0A7010F4	kurt@arrowsp.net	26.4	completed	2025-02-20 14:51:06.942926	816953	BROOKLAND SOFTBALL
258	DTF-5A71DE17	capmanoffice@yahoo.com	120.2	completed	2025-02-18 21:16:30.649912	816954	021825
277	DTF-953E7249	kurt@arrowsp.net	216	completed	2025-02-20 15:22:48.531203	816953	BRAD BAKER 5k
278	DTF-7F7D2E06	rickey.stitchscreen@gmail.com	178.52	completed	2025-02-20 19:15:04.346093	816980	Printers Ink 
279	DTF-1BAB9DB9	kurt@arrowsp.net	0.44	completed	2025-02-21 14:41:43.793084	816953	NETTLETON SOCCER
280	DTF-DECFFA21	capmanoffice@yahoo.com	27.16	completed	2025-02-21 14:42:32.099796	816954	022125
281	DTF-FD952916	Blair@elitepp.com	19.86	completed	2025-02-21 16:19:57.5006	817002	37488
282	DTF-95F846D7	kurt@arrowsp.net	4.62	completed	2025-02-21 16:57:40.185632	816953	ELIZABETH T-SHIRTS
154	DTF-46645B13	capmanoffice@yahoo.com	20.22	completed	2025-02-13 21:50:42.45838	816872	021325
\.


--
-- Data for Name: order_item; Type: TABLE DATA; Schema: public; Owner: neondb_owner
--

COPY public.order_item (id, order_id, file_key, width_inches, height_inches, quantity, cost, notes) FROM stdin;
325	154	Monroe_4H_OH.11.png	3.03	3.41	11	1.98	
326	154	Monroe_4H_SLEEVE.11.png	3.41	1.86	11	1.3199999999999998	
327	154	DELTA_REMODELING_OH_Charcoal.6.png	3.01	2.97	6	1.08	
328	154	DELTA_REMODELING_BACK_Charcoal.6.png	10.58	12.11	6	15.84	
673	227	Bucy_Farms_cap_BLACK.png	2.05	1.75	10	0.8	
674	227	GCT_Swim_25_CHEST.png	11.8	10.2	25	60	
675	227	GCT_Swim_25_NAMES.png	7.42	11.66	25	42	
676	227	SpencerTire_OH_WHITE.png	3.75	1.93	15	2.4	
677	227	SpencerTire_BACK_WHITE.png	11.5	5.92	15	21.599999999999998	
678	227	Spencer_Tire_Silver_Car_BACK.png	11.85	9.05	9	19.44	
679	227	Spencer_Tire_Red_Car_BACK.png	11.85	9.05	10	21.6	
680	227	SpencerTire_OH_Red_Black.png	3.75	1.93	10	1.6	
681	227	SpencerTire_OH_White_Black.png	3.75	1.93	9	1.44	
682	227	Zaks_Carwash_OH.png	3.5	1.17	12	0.96	
683	227	Zaks_Carwash_BACK.png	9.75	5.36	12	12	
684	228	BROOKLAND_SOCCER_-_LEFT_CHEST_-_ORANGE_GOALIE_-_QTY_-_1.png	3.5	3.5	1	0.32	
685	228	BROOKLAND_SOCCER_-_NUMBER_2_-_BACK_-_QTY_-_1.png	3.66	6.02	1	0.48	
686	228	BROOKLAND_SOCCER_-_NUMBER_2_-_FRONT_-_QTY_-_1.png	2.44	4	1	0.16	
710	238	DTF-9D658C2D-1_NUCKLES__SON_PLUMBING_-_QTY_-_1_qty-1.png	12	8.97	1	2.16	
711	239	DTF-47E20254-1_DELTA_T_-_ARKANSAS_MATCHBOX_-_QTY_-_76_qty-76.png	11.65	15	76	273.6	
712	240	DTF-C29DC5EB-1_DELTA_T_-_ARKANSAS_CHARM_-_QTY_-_50_qty-50.png	11.5	9.8	50	120	
713	241	DTF-476DB723-1_DELTA_T_-_NO_LUCK_JUST_JESUS_-_QTY_-_40_qty-40.png	11	11.64	40	105.60000000000001	
714	242	DTF-ED0E8D22-1_DELTA_T_-_CITIZEN_OF_HEAVEN_-_QTY_-_40_qty-40.png	11	9.91	40	88	
715	243	DTF-3BD59F4D-1_NUCKLES__SON_PLUMBING_-_LEFT_CHEST_-_QTY_-_1_qty-1.png	4.25	2.23	1	0.16	
717	245	DTF-8C34C95F-1_MCCAULEY_AUCTIONS_-_QTY_-_1_qty-1.png	3.81	1.56	1	0.16	
718	245	DTF-8C34C95F-2_MARKED_TREE_INDIAN_HEAD_-_ADULT_-_QTY_-_5_qty-5.png	10	9.59	5	10	
719	245	DTF-8C34C95F-3_MARKED_TREE_INDIAN_HEAD_-_YOUTH_-_QTY_-_3_qty-3.png	9	8.63	3	4.86	
720	245	DTF-8C34C95F-4_MARKED_TREE_SPONSORS_-_FULL_BACK_-_ADULT_-_QTY_-_5_qty-5.png	11.01	12.48	5	13.200000000000001	
721	245	DTF-8C34C95F-5_MARKED_TREE_SPONSORS_-_FULL_BACK_-_YOUTH_-_QTY_-_3_qty-3.png	10.01	11.34	3	6.6000000000000005	
722	245	DTF-8C34C95F-6_VALLEY_VIEW_BASEBALL_WITH_GLOVE_-_FULL_FRONT_-_QTY_-_1_qty-1.png	9.5	2.19	1	0.4	
723	245	DTF-8C34C95F-7_VALLEY_VIEW_BASEBALL_-_LEFT_CHEST_-_QTY_-_1_qty-1.png	3.79	3	1	0.24	
725	247	DTF-A5F2929D-1_VALLEY_VIEW_BASEBALL_-_FULL_FRONT_-_QTY_-_1_qty-1.png	10.46	2.9	1	0.6	IF POSSIBLE, DELETE THE DESIGN LIKE THIS THAT I SENT THAT WAS SLANTED.  CUSTOMER WANTS IT STRAIGHT.  UGH..
726	248	DTF-685FAE1E-1_GUILLEN_ROOFING_-_QTY_-_5_qty-5.png	3.5	2.12	5	0.8	
727	248	DTF-685FAE1E-2_GUILLEN_ROOFING_-_FULL_BACK_-_QTY_-_5_qty-5.png	11	8.78	5	9.9	
728	249	DTF-8B4F5212-1_Tri_State_MC_OH_GREY_qty-3.png	3.86	2.23	3	0.48	
729	249	DTF-8B4F5212-2_Tri_State_MC_Back_GREY_qty-3.png	10.84	11.67	3	7.92	
730	249	DTF-8B4F5212-3_JCM_Farms_OH_WHITE_qty-3.png	3.07	1.79	3	0.36	
731	249	DTF-8B4F5212-4_JCM_Farms_Back_WHITE_qty-3.png	11.76	8.54	3	6.48	
732	249	DTF-8B4F5212-5_JCM_Farms_OH_NAVY_qty-3.png	3.07	1.8	3	0.36	
733	249	DTF-8B4F5212-6_JCM_Farms_Back_NAVY_qty-3.png	11.76	8.54	3	6.48	
734	249	DTF-8B4F5212-7_JCM_Farms_OH_BONE_qty-6.png	3.07	1.8	6	0.72	
735	249	DTF-8B4F5212-8_JCM_Farms_Back_BONE_qty-6.png	11.76	8.54	6	12.96	
736	249	DTF-8B4F5212-9_Porkasaurus_Rex_cap_FILL_qty-13.png	2.61	2.25	13	1.56	
737	249	DTF-8B4F5212-10_Porkasaurus_Rex_cap_NO_FILL_qty-7.png	2.64	2.25	7	0.84	
738	249	DTF-8B4F5212-11_VelvetFray_VF_bag_WHITE_qty-25.png	8.69	8	25	36	
739	249	DTF-8B4F5212-12_VelvetFray_VF_OH_WHITE_qty-21.png	3.5	3.22	21	5.04	
740	249	DTF-8B4F5212-13_VelvetFray_back_WHITE_qty-46.png	12.5	6.85	46	83.72	
741	249	DTF-8B4F5212-14_VelvetFray_SG_Chest_WHITE_qty-16.png	11	5.77	16	21.12	
742	249	DTF-8B4F5212-15_VelvetFray_SG_Sleeve_WHITE_qty-16.png	12.85	3.76	16	16.64	
743	250	DTF-7D762B2F-1_HDZ_CONSTRUCTION_-_LEFT_CHEST_-_QTY_-_30_qty-30.png	3.5	3.47	30	7.199999999999999	
744	250	DTF-7D762B2F-2_HDZ_CONSTRUCTION_-_FULL_BACK_-_QTY_-_30_qty-30.png	11	11.93	30	79.2	
748	254	DTF-280ECB14-1_HAVOC_SOFTBALL_-_MATTHEWS_NUMBER_11_-_QTY_-_1_qty-1.png	10	9.98	1	2	
764	258	DTF-5A71DE17-1_Harvest_RaisedtoLife_qty-52.png	10.09	11.25	52	114.4	
765	258	DTF-5A71DE17-2_PHS_Softball_25_ROYAL_qty-5.png	11	4.99	5	5.5	
766	258	DTF-5A71DE17-3_Ridgeway_Siding_sleeve_WHITE_qty-5.png	3	1.14	5	0.3	
778	269	DTF-9DD6A873-1_CAMP_QUALITY_-_LEFT_SLEEVE_-_BLACK_-_QTY_-_81_qty-81.png	1.94	3	81	9.719999999999999	
784	275	DTF-05F402C6-1_ENCOMPASS_-_CEO_-_QTY_-_1_qty-1.png	3.5	1.85	1	0.16	
785	275	DTF-05F402C6-2_ENCOMPASS_-_OT_-_QTY_-_1_qty-1.png	4	2.03	1	0.16	
786	275	DTF-05F402C6-3_ENCOMPASS_-_EVS_-_QTY_-_1_qty-1.png	3.15	1.72	1	0.12	
787	275	DTF-05F402C6-4_ENCOMPASS_-_LPN_-_QTY_-_1_qty-1.png	2.98	2.14	1	0.12	
788	275	DTF-05F402C6-5_ENCOMPASS_-_COMPASS_-_BLACK_-_QTY_-_1_qty-1.png	12	13.56	1	3.36	
789	275	DTF-05F402C6-6_ENCOMPASS_-_COTA_-_QTY_-_2_qty-2.png	3.25	2.02	2	0.24	
790	275	DTF-05F402C6-7_ENCOMPASS_-_CRRN_-_QTY_-_2_qty-2.png	3.3	1.99	2	0.24	
791	275	DTF-05F402C6-8_ENCOMPASS_-_PT_-_QTY_-_2_qty-2.png	3.25	1.9	2	0.24	
792	275	DTF-05F402C6-9_ENCOMPASS_-_RN_-_QTY_-_3_qty-3.png	3.26	1.75	3	0.36	
793	276	DTF-0A7010F4-1_BROOKLAND_SOFTBALL_-_QTY_-_30_qty-30.png	11	3.86	30	26.4	
794	277	DTF-953E7249-1_BRAD_BAKER_5k_-_QTY_-_150_qty-150.png	9	7.99	150	216	Y'all should have this design from approx 2/20/24.  The white box behind Brad's face should be eliminated.  OK?
795	278	DTF-7F7D2E06-1_tech_softball_2025_numbers_qty-3.png	44.22	10.08	3	26.400000000000002	
796	278	DTF-7F7D2E06-2_tech_jr_high_softball_logo_qty-14.png	10.88	6.65	14	21.560000000000002	
797	278	DTF-7F7D2E06-3_Tech_jr_high_softball_numbers_qty-1.png	49.09	16.82	1	16.66	
798	278	DTF-7F7D2E06-4_Tech_softball_hoodie_logo_2025_qty-30.png	10	10.09	30	60	
799	278	DTF-7F7D2E06-5_tech_softball_logo_2025_qty-35.png	11.07	6.97	35	53.9	
800	279	DTF-1BAB9DB9-1_NETTLETON_SOCCER_-_PENDLETON_-_QTY_-_1_qty-1.png	10.5	2	1	0.44	
801	280	DTF-DECFFA21-1_Winwater_sleeve_WHITE_qty-2.png	3.02	0.73	2	0.12	
802	280	DTF-DECFFA21-2_Winwater_sleeve_ROYAL_qty-2.png	3.03	0.73	2	0.12	
803	280	DTF-DECFFA21-3_Winwater_Keyle_WHITE_qty-2.png	2.07	0.81	2	0.08	
804	280	DTF-DECFFA21-4_Winwater_Keyle_ROYAL_qty-2.png	2.08	0.81	2	0.08	
805	280	DTF-DECFFA21-5_Landon_bachelor_koozie_qty-15.png	2.85	2.49	15	1.7999999999999998	
806	280	DTF-DECFFA21-6_Arrows_Therapy_White_OH_qty-13.png	2.85	3.97	13	3.12	
807	280	DTF-DECFFA21-7_Arrows_Compassionate_Care_BACK_qty-13.png	7.33	12	13	21.84	
808	281	DTF-FD952916-1_NEA-SURGE_Cap_qty-2.png	2	2	2	0.16	Add Extra White Under base
809	281	DTF-FD952916-2_NEA-SURGE_FullFront_34128__qty-13.png	8	8	13	16.64	Add Extra White Under base
810	281	DTF-FD952916-3_NEA-SURGE_LeftChest__qty-17.png	3	3	17	3.06	Add Extra White Under base
811	282	DTF-95F846D7-1_ELIZABETH_T_-_LEFT_CHEST_-_QTY_-_4_qty-4.png	2.22	3.4	4	0.48	
812	282	DTF-95F846D7-2_ELIZABETH_T_-_FULL_BACK_-_HEART_-_QTY_-_1_qty-1.png	8.84	11.55	1	2.16	
813	282	DTF-95F846D7-3_ELIZABETH_T_-_FULL_BACK_-_BLESSED_-_QTY_-_3_qty-3.png	2.7	11.45	3	1.98	
814	283	DTF-08944E59-1_LIONS_-_NAME_SAMPLES_-_QTY_-_1_qty-1.png	3.25	4.74	1	0.3	
815	284	DTF-187394D5-1_Jones_Concrete_OH_BLACK_BONE_qty-5.png	3.85	1.79	5	0.8	
816	284	DTF-187394D5-2_Jones_Concrete_Back_BLACK_BONE_qty-5.png	11.62	6.05	5	7.199999999999999	
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: neondb_owner
--

COPY public.users (id, username, email, password_hash, is_admin) FROM stdin;
1	admin	admin@appareldecorating.net	scrypt:32768:8:1$8Xuv3s31HuzQvEYM$24f80388ae861e65b8632251f1a1b69f9ad7e4d4dbdbc6095acf141e68a253fe3957106912d84eff962c08af9eb6287d75b98c079ec362abcfd557e767d16766	t
\.


--
-- Name: order_id_seq; Type: SEQUENCE SET; Schema: public; Owner: neondb_owner
--

SELECT pg_catalog.setval('public.order_id_seq', 284, true);


--
-- Name: order_item_id_seq; Type: SEQUENCE SET; Schema: public; Owner: neondb_owner
--

SELECT pg_catalog.setval('public.order_item_id_seq', 816, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: neondb_owner
--

SELECT pg_catalog.setval('public.users_id_seq', 1, true);


--
-- Name: order_item order_item_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.order_item
    ADD CONSTRAINT order_item_pkey PRIMARY KEY (id);


--
-- Name: order order_order_number_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public."order"
    ADD CONSTRAINT order_order_number_key UNIQUE (order_number);


--
-- Name: order order_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public."order"
    ADD CONSTRAINT order_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: order_item order_item_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.order_item
    ADD CONSTRAINT order_item_order_id_fkey FOREIGN KEY (order_id) REFERENCES public."order"(id);


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO neon_superuser WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON TABLES TO neon_superuser WITH GRANT OPTION;


--
-- PostgreSQL database dump complete
--

